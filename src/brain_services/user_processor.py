"""每用户一个处理类 — 消息串行处理（多条 @ 合并）+ 记忆总结 + 主动发言

用户策略相关的所有后台行为都归 UserProcessor 管理，每用户三个 daemon 线程：

- 处理线程：消息队列串行处理。LLM 处理耗时即批次积累窗口——处理第一条时
  后续到达的消息自然在队列里堆积，处理完取出全部作为一批，多条 @ 消息合并
  成一条 user 消息一次 LLM、一次回复（避免各答各的内容重复）。
- 总结线程：低频 sleep 循环做增量中期记忆总结（不写 chat_messages，无 tool
  链路，与处理线程并发安全）。
- 破冰线程：低频 sleep 循环检查冷场并主动发言（同左，`tools=[]` 无 tool 链路）。

UserProcessorManager 是注册表：活跃用户懒创建；启用了破冰的用户（冷场时
无消息到达，必须常驻）由 sync_candidates 预创建。
"""
import os
import time
import uuid
import queue
import random
import logging
import threading
import requests
from collections import deque
from datetime import datetime

from src.common.utils import cfg
from src.common.schemas.agent_request import AgentRequest, ProtocolType, ContentType
from src.common.utils.tracer import trace_event, trace_reply as _trace_reply
from .strategy import strategy_engine
from .strategy.context_builder import LLMContextBuilder
from .strategy.llm_handler import LLMHandler
from .stats import stats
from .status import ai_status
from .gateway_sender import send_wechat_text, send_wechat_file, send_voice_text

logger = logging.getLogger("brain_services.user_processor")

# 总结/破冰 tick 间隔（对齐原 summarizer 30min / ice_breaker 30~40min 随机）
_SUMMARIZE_INTERVAL = 1800
_ICE_BREAKER_INTERVAL = 1800
_ICE_BREAKER_JITTER = 600


class _MessageQueue:
    """支持 peek 的线程安全 FIFO（批次收集需查看队头类型而不取出）"""

    def __init__(self):
        self._deque: deque = deque()
        self._cv = threading.Condition()

    def put(self, item):
        with self._cv:
            self._deque.append(item)
            self._cv.notify()

    def get(self):
        """阻塞取队头（stop 时由 put(None) 哨兵唤醒）"""
        with self._cv:
            while not self._deque:
                self._cv.wait()
            return self._deque.popleft()

    def peek(self):
        """非阻塞查看队头（空则抛 queue.Empty）"""
        with self._cv:
            if not self._deque:
                raise queue.Empty
            return self._deque[0]

    def pop(self):
        """非阻塞取队头（空则抛 queue.Empty）"""
        with self._cv:
            if not self._deque:
                raise queue.Empty
            return self._deque.popleft()


class UserProcessor:
    """单用户的消息处理 + 记忆总结 + 主动发言"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._queue = _MessageQueue()
        self._running = True
        self._engine = strategy_engine
        self.context_builder = LLMContextBuilder()
        self.llm_handler = LLMHandler()
        self._bot_name = os.getenv("WECHAT_BOT_NAME", "")
        # 破冰状态（纯内存，重启归零 = 原 ice_breaker 行为）
        self._ib_state = {
            "last_proactive_time": time.time(),
            "msg_id_at_send": 0,
            "attempt_date": "",
        }
        # 用户信息缓存（sync_candidates 预填，缺失时补查 /api/users/{uid}）
        self._wechat_name = ""
        self._user_type = "person"

        # 三个线程
        self._process_thread = threading.Thread(
            target=self._process_loop, daemon=True,
            name=f"up-msg-{user_id[:12]}")
        self._summarize_thread = threading.Thread(
            target=self._summarize_loop, daemon=True,
            name=f"up-sum-{user_id[:12]}")
        self._ice_thread = threading.Thread(
            target=self._ice_breaker_loop, daemon=True,
            name=f"up-ice-{user_id[:12]}")
        self._process_thread.start()
        self._summarize_thread.start()
        self._ice_thread.start()

    # ---- 消息处理线程 ----

    def enqueue(self, req: AgentRequest):
        """消息入队（agent 路由调用）"""
        self._queue.put(req)

    def _process_loop(self):
        """处理线程：从队列头部按类型连续取批，类型不同留在队列

        - smart 用户且 batch_enabled 开启：取出的批次中，wechat 合并处理
          （多条消息一次 LLM），非 wechat（voice/web）一条一条处理
        - direct/ignore 用户，或 batch_enabled 关闭：无论队列多少条，
          顺序一条一条处理（单条完整链路）
        - 严格 FIFO：peek 队头只查看不取出，类型不同的消息保持原位
        """
        while self._running:
            try:
                req = self._queue.get()  # 阻塞取第一条
                if req is None:  # stop 哨兵
                    break
                config = self._engine.get_user_config(self.user_id)
                if config.get("strategy") != "smart" or not config.get("batch_enabled", False):
                    # direct/ignore 或用户关闭 batch：顺序一条一条处理
                    self._process_single(req)
                    continue

                # smart + batch：连续取同协议消息组批（LLM 处理耗时即积累窗口）
                batch = [req]
                proto = req.protocol
                while True:
                    try:
                        nxt = self._queue.peek()
                    except queue.Empty:
                        break  # 队列取完
                    if nxt.protocol != proto:
                        break  # 类型不同留在队列，下次再取
                    self._queue.pop()
                    batch.append(nxt)

                # 处理批次：wechat 批量链路；非 wechat 一条一条处理
                if proto == ProtocolType.WECHAT:
                    self._process_batch(batch, config)
                else:
                    for r in batch:
                        self._process_single(r)
            except Exception as e:
                logger.error("用户 %s 处理线程异常: %s", self.user_id, e, exc_info=True)

    def _process_single(self, req: AgentRequest):
        """单条完整链路：追踪 → engine.process（记录/OCR/策略分流全流程）→ 收尾"""
        logger.info("[DEBUG] _process_single 入口 metadata: %s", dict(req.metadata or {}))
        trace_event(req.request_id, "brain_receive",
                    protocol=req.protocol.value, user_id=req.user_id,
                    metadata={"content": req.content or ""})
        try:
            resp = self._engine.process(req)
            self._deliver(req, resp)
        except Exception as e:
            logger.error("用户 %s 单条处理异常 %s: %s",
                         self.user_id, req.request_id, e, exc_info=True)
            ai_status.set("idle")

    def _process_batch(self, reqs: list[AgentRequest], config: dict):
        """wechat 批次链路：追踪 → engine.process_batch（记录/OCR/分组/合并全在
        engine 批量链路内）→ 收尾（skip 清理、从请求 merged 标记、一次回复）"""
        if not reqs:
            return
        logger.info("用户 %s 批次处理: 队列=%d 条", self.user_id, len(reqs))

        # 1. 逐条追踪（记录/OCR/分组在 engine.process_batch 内）
        for req in reqs:
            trace_event(req.request_id, "brain_receive",
                        protocol=req.protocol.value, user_id=req.user_id,
                        metadata={"content": req.content or ""})

        # 2. engine 批量链路
        try:
            result = self._engine.process_batch(reqs, config)
        except Exception as e:
            logger.error("用户 %s 批次处理异常: %s", self.user_id, e, exc_info=True)
            for req in reqs:
                self._cleanup_trace(req)
            ai_status.set("idle")
            return

        # 3. 收尾：skip 消息清理追踪
        skipped = result.get("skipped") or []
        for req, _mid, _ocr in skipped:
            self._cleanup_trace(req)

        resp = result.get("resp")
        if resp is None:
            ai_status.set("idle")
            return
        actionable = result.get("actionable") or []
        first, _fmid, _focr = actionable[0]
        self._deliver_merged(first, resp, actionable)

    # ---- 收尾 ----

    def _cleanup_trace(self, req):
        """删除请求追踪（跳过/ignored 时）"""
        try:
            url = cfg.get_service_url("db_services", f"/api/request-traces/{req.request_id}")
            requests.delete(url, timeout=3)
        except Exception:
            pass

    def _mark_merged(self, others, error: str = ""):
        """被合并的从请求标记 merged + skip（相当于 skip：已并入批次，未独立回复）"""
        meta = {"batch_size": len(others) + 1}
        if error:
            meta["error"] = error
        for req, _mid, _ocr in others:
            trace_event(req.request_id, "merged", metadata=meta,
                        protocol=req.protocol.value, user_id=req.user_id)
            _trace_reply(req.request_id, skip=True)

    def _deliver(self, req: AgentRequest, resp):
        """单条回复收尾（迁移自原 agent._process_async_locked）"""
        if not resp.data or resp.data.get("skipped") or resp.data.get("ignored"):
            logger.info("请求 %s 跳过，清理追踪", req.request_id[:12])
            self._cleanup_trace(req)
            ai_status.set("idle")
            return

        text = (resp.data or {}).get("text", "")
        is_skip = text and text.strip() == "__SKIP__"
        stats.record_request(answered=not is_skip)

        if not is_skip:
            token_meta = {
                "prompt_tokens": req.metadata.get("prompt_tokens", 0),
                "completion_tokens": req.metadata.get("completion_tokens", 0),
            }
            trace_event(req.request_id, "brain_done", protocol=req.protocol.value,
                        user_id=req.user_id, metadata=token_meta)
            if text:
                _trace_reply(req.request_id, reply=text)
            ai_status.set("speaking", message=text[:80] if text else "")
        else:
            _trace_reply(req.request_id, skip=True)
            ai_status.set("idle")
            return

        who = req.metadata.get("wechat_name", "")
        if text and req.protocol == ProtocolType.WECHAT and who:
            send_wechat_text(who, text)
            ai_status.set("idle")
        elif text and req.protocol == ProtocolType.VOICE:
            wakeword_id = (req.metadata or {}).get("wakeword_id", "")
            send_voice_text(text, wakeword_id, req.request_id)
            # 语音 idle 由 speak.py 播放完后设置

        files = (resp.data or {}).get("files", [])
        if files and who:
            for fp in files:
                if os.path.exists(fp):
                    send_wechat_file(who, fp)
                    try:
                        os.remove(fp)
                    except Exception:
                        pass

        # 非语音非微信（如 WEB 管理后台）→ 直接空闲
        if req.protocol not in (ProtocolType.VOICE, ProtocolType.WECHAT):
            ai_status.set("idle")

    def _deliver_merged(self, first: AgentRequest, resp, pending):
        """合并批收尾：从请求标记 merged+skip；主请求一次回复"""
        self._mark_merged(pending[1:])

        text = (resp.data or {}).get("text", "")
        is_skip = text and text.strip() == "__SKIP__"
        stats.record_request(answered=not is_skip)
        token_meta = {
            "prompt_tokens": first.metadata.get("prompt_tokens", 0),
            "completion_tokens": first.metadata.get("completion_tokens", 0),
        }
        if not is_skip:
            trace_event(first.request_id, "brain_done", protocol=first.protocol.value,
                        user_id=first.user_id, metadata=token_meta)
            if text:
                _trace_reply(first.request_id, reply=text)
            ai_status.set("speaking", message=text[:80] if text else "")
        else:
            _trace_reply(first.request_id, skip=True)
            ai_status.set("idle")
            return

        who = first.metadata.get("wechat_name", "")
        if text and who:
            send_wechat_text(who, text)
            ai_status.set("idle")
        files = (resp.data or {}).get("files", [])
        if files and who:
            for fp in files:
                if os.path.exists(fp):
                    send_wechat_file(who, fp)
                    try:
                        os.remove(fp)
                    except Exception:
                        pass

    # ---- 记忆总结线程 ----

    def _summarize_loop(self):
        """总结线程：低频 sleep 循环，增量总结（无新消息零成本跳过）"""
        while self._running:
            time.sleep(_SUMMARIZE_INTERVAL)
            try:
                self.summarize(force=False)
            except Exception as e:
                logger.error("用户 %s 总结异常: %s", self.user_id, e, exc_info=True)

    def summarize(self, force: bool = False, window: int | None = None):
        """增量中期总结（迁移自 summarizer._do_incremental_summary）

        Args:
            force: True=跳过 last_msg_id 与窗口检查（全量重总结，手动触发用）
            window: 窗口分钟数；None=用用户配置 short_term_window
        """
        user_id = self.user_id
        if window is None:
            window = self._engine.get_user_config(user_id).get("short_term_window", 30)

        # 1. 查已总结到的最大 msg_id
        try:
            url = cfg.get_service_url("db_services", f"/api/chat-summaries/{user_id}/max-msg-id")
            resp = requests.get(url, timeout=10)
            summarized_max = resp.json().get("max_id", 0) if resp.status_code == 200 else 0
        except Exception:
            summarized_max = 0

        # 2. 获取旧总结内容（如有）
        old_summary = ""
        try:
            url = cfg.get_service_url("db_services", f"/api/chat-summaries/{user_id}/latest")
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                old_summary = resp.json().get("summary", "")
        except Exception:
            pass

        # 3. 查当前最大 msg_id
        try:
            url = cfg.get_service_url("db_services", f"/api/chat-messages/{user_id}/max-id")
            resp = requests.get(url, timeout=10)
            current_max = resp.json().get("max_id", 0) if resp.status_code == 200 else 0
        except Exception:
            return

        # 4. 没有新消息 → 跳过（除非 force）
        if not force and current_max <= summarized_max:
            logger.debug("用户 %s 无新消息，跳过总结", user_id)
            return

        # 5. 加载 summarized_max 之后的新消息
        try:
            url = cfg.get_service_url("db_services", f"/api/chat-messages/{user_id}")
            resp = requests.get(url, params={"since_id": summarized_max, "limit": 500}, timeout=15)
            if resp.status_code != 200:
                return
            messages = resp.json().get("messages", [])
        except Exception as e:
            logger.error("获取用户 %s 聊天记录失败: %s", user_id, e)
            return

        # 窗口过滤（非 force 模式只总结窗口之前的消息）
        if not force and window > 0:
            import datetime as _dt
            cutoff = (_dt.datetime.utcnow() - _dt.timedelta(minutes=window))
            messages = [m for m in messages
                        if m.get("created_at", "") < cutoff.strftime("%Y-%m-%d %H:%M:%S")]

        if not messages:
            logger.debug("用户 %s 窗口内无过期消息，跳过总结", user_id)
            return

        # 6. 组装 prompt：旧总结 + 新消息
        log_lines = []
        if old_summary:
            log_lines.append(f"【之前的总结】\n{old_summary}\n")
        log_lines.append("【新增聊天记录】")
        for m in messages:
            role = m.get("role", "?")
            content = (m.get("content") or "")[:200]
            tool = m.get("tool_name", "")
            if tool:
                log_lines.append(f"[{role} 调用 {tool}]: {content}")
            else:
                log_lines.append(f"[{role}]: {content}")

        log_text = "\n".join(log_lines)
        if not log_text.strip():
            return

        prompt = (
            "你是一个对话摘要助手。请将之前的总结和新增的聊天记录合并为一份新的简洁总结，"
            "保留重要的事件、决定、用户偏好和关键信息。"
            "如果总字数超过 800 字，允许丢弃一些不重要的旧信息。"
            f"用中文，控制在 800 字以内。\n\n{log_text}"
        )
        summary = self._engine.llm_handler.deepseek.ask_single_question(prompt, timeout=30)
        if not summary:
            logger.warning("用户 %s 总结生成失败", user_id)
            return
        summary = summary[:1000]

        # 7. 存入 chat_summaries
        try:
            url = cfg.get_service_url("db_services", "/api/chat-summaries")
            resp = requests.post(url, json={
                "user_id": user_id,
                "summary": summary,
                "last_msg_id": current_max,
            }, timeout=10)
            if resp.status_code == 201:
                logger.info("用户 %s 增量总结完成: %d 条新消息 → %d 字",
                            user_id, len(messages), len(summary))
        except Exception as e:
            logger.error("保存总结失败: %s", e)

    # ---- 主动发言线程 ----

    def _ice_breaker_loop(self):
        """破冰线程：低频 sleep 循环，冷场检查"""
        while self._running:
            time.sleep(_ICE_BREAKER_INTERVAL + random.randint(0, _ICE_BREAKER_JITTER))
            try:
                self._check_ice_breaker()
            except Exception as e:
                logger.error("用户 %s 破冰检查异常: %s", self.user_id, e, exc_info=True)

    def _check_ice_breaker(self):
        """检查是否需要主动发言（迁移自 ice_breaker._check_group）"""
        user_id = self.user_id
        config = self._engine.get_user_config(user_id)
        if not config.get("ice_breaker_enabled"):
            return
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        wechat_name = self._wechat_name
        if not wechat_name:
            try:
                url = cfg.get_service_url("db_services", f"/api/users/{user_id}")
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    wechat_name = data.get("wechat_name", "")
                    self._user_type = data.get("user_type") or self._user_type
            except Exception:
                pass
            if not wechat_name:
                logger.warning("用户 %s 无 wechat_name，跳过破冰", user_id)
                return

        # 1. 夜间模式
        if self._is_night_mode(config, now):
            logger.debug("[%s] 免打扰时段，跳过", wechat_name)
            return

        state = self._ib_state
        # 2. 当天已尝试且无人回应 → 跳过
        if state["attempt_date"] == today:
            logger.debug("[%s] 今日已尝试且无人回应，跳过", wechat_name)
            return

        # 3. 获取最新消息时间
        latest = self._get_latest_message(user_id)
        if not latest:
            logger.debug("[%s] 无聊天记录，跳过", wechat_name)
            return
        latest_time_str = latest.get("created_at", "")
        try:
            latest_time = datetime.strptime(latest_time_str, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return

        idle_sec = (now - latest_time).total_seconds()
        trigger_minutes = config.get("ice_breaker_trigger_minutes", 15)
        logger.debug("[%s] 空闲 %.1f 分钟 (阈值=%d)", wechat_name, idle_sec / 60, trigger_minutes)

        # 4. 冷场检查
        if idle_sec < trigger_minutes * 60:
            logger.debug("[%s] 未冷场，跳过", wechat_name)
            return

        # 5. 冷却检查
        cooldown_minutes = config.get("ice_breaker_cooldown_minutes", 60)
        elapsed_min = (time.time() - state["last_proactive_time"]) / 60
        if elapsed_min < cooldown_minutes:
            logger.debug("[%s] 冷却中: 已过 %.1f min < %d min",
                         wechat_name, elapsed_min, cooldown_minutes)
            return
        logger.debug("[%s] 冷却通过: 已过 %.1f min", wechat_name, elapsed_min)

        # 6. 上次破冰后是否有人回应
        if state["msg_id_at_send"] and state["attempt_date"]:
            has_resp = self._has_user_response(user_id, state["msg_id_at_send"])
            logger.debug("[%s] 检查回应: msg_id_at_send=%d, has_response=%s",
                         wechat_name, state["msg_id_at_send"], has_resp)
            if not has_resp:
                state["attempt_date"] = today
                logger.info("[%s] 上次破冰无人回应，今日跳过", wechat_name)
                return
            logger.info("[%s] 上次破冰有人回应，重置状态", wechat_name)
            state["msg_id_at_send"] = 0
            state["attempt_date"] = ""

        # 7. 发送破冰！
        logger.info("[%s] 破冰触发! 静默 %.1f 分钟",
                    wechat_name, (now - latest_time).total_seconds() / 60)
        self._generate_and_send(user_id, wechat_name, config, latest)

        state["last_proactive_time"] = time.time()
        state["msg_id_at_send"] = latest.get("id", 0)
        state["attempt_date"] = today

    def generate_and_send(self, wechat_name: str, prompt_override: str = ""):
        """公开接口：立即生成并发送主动发言（测试用）"""
        config = {"ice_breaker_prompt": prompt_override} if prompt_override else {}
        if not config.get("ice_breaker_prompt"):
            try:
                url = cfg.get_service_url("db_services", f"/api/user-configs/{self.user_id}")
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    config = resp.json()
            except Exception:
                pass
        if not config.get("user_type"):
            config["user_type"] = self._user_type or "person"
        self._generate_and_send(self.user_id, wechat_name, config, {})

    def _generate_and_send(self, user_id: str, wechat_name: str, config: dict, latest_msg: dict):
        """用 LLM 生成主动发言消息并发送（迁移自 ice_breaker._generate_and_send）"""
        try:
            # 保证有 system_prompt（candidates 端点通常带，测试入口可能缺）
            if not config.get("system_prompt"):
                try:
                    url = cfg.get_service_url("db_services", f"/api/user-configs/{user_id}")
                    resp = requests.get(url, timeout=10)
                    if resp.status_code == 200:
                        config = resp.json()
                except Exception:
                    pass

            user_type = config.get("user_type") or self._user_type or "person"
            # 触发语：ice_breaker_prompt 自定义，空则用默认
            trigger = config.get("ice_breaker_prompt", "").strip()
            if not trigger:
                if user_type == "group":
                    trigger = "群里冷场了，请主动说点什么活跃气氛。"
                else:
                    trigger = "好久没聊天了，说点什么吧。"

            # 群聊需要 @bot_name 绕过 group_at_only 检查
            if user_type == "group" and self._bot_name:
                current_msg = f"@{self._bot_name} {trigger}"
            else:
                current_msg = trigger

            chat_type = "group" if user_type == "group" else "private"
            # 短期窗口设大（8h），确保冷场后还能加载到最近聊天记录
            ctx_config = {**config, "short_term_window": 480}

            messages = self.context_builder.build(
                user_id=user_id,
                config=ctx_config,
                current_msg=current_msg,
                protocol="wechat",
                chat_type=chat_type,
            )
            # LLM 生成（不调用工具）
            reply, _, _ = self.llm_handler.handle(
                user_id=user_id,
                messages=messages,
                tools=[],
                request_id=f"ice_{uuid.uuid4().hex[:12]}",
            )
            if reply and reply.strip():
                send_wechat_text(wechat_name, reply.strip())
            else:
                logger.warning("主动发言回复为空，%s", user_id)
        except Exception as e:
            logger.error("主动发言生成/发送失败 %s: %s", user_id, e, exc_info=True)

    # ---- 辅助 ----

    def _is_night_mode(self, config: dict, now: datetime) -> bool:
        """检查当前时间是否在免打扰时段内（迁移自 ice_breaker）"""
        sleep_start = config.get("ice_breaker_sleep_start", "01:00")
        sleep_end = config.get("ice_breaker_sleep_end", "08:00")
        try:
            ps = [int(x) for x in sleep_start.split(":")]
            pe = [int(x) for x in sleep_end.split(":")]
            start_t = now.replace(hour=ps[0], minute=ps[1], second=0, microsecond=0)
            end_t = now.replace(hour=pe[0], minute=pe[1], second=0, microsecond=0)
            if start_t < end_t:
                return start_t <= now < end_t
            else:
                return now >= start_t or now < end_t
        except Exception:
            return False

    def _get_latest_message(self, user_id: str) -> dict | None:
        """查询用户最新一条消息"""
        try:
            url = cfg.get_service_url("db_services", f"/api/chat-messages/{user_id}")
            resp = requests.get(url, params={"limit": 1}, timeout=10)
            if resp.status_code == 200:
                msgs = resp.json().get("messages", [])
                # API 返回正序排列，最后一条是最新的
                return msgs[-1] if msgs else None
        except Exception as e:
            logger.error("查询 %s 最新消息失败: %s", user_id, e)
        return None

    def _has_user_response(self, user_id: str, since_id: int) -> bool:
        """检查 since_id 之后是否有真实的用户消息（排除破冰触发消息）"""
        try:
            url = cfg.get_service_url("db_services", f"/api/chat-messages/{user_id}")
            resp = requests.get(url, params={"since_id": since_id, "limit": 50}, timeout=10)
            if resp.status_code == 200:
                msgs = resp.json().get("messages", [])
                for msg in msgs:
                    if msg.get("role") != "user":
                        continue
                    content = (msg.get("content") or "").strip()
                    # 跳过破冰触发消息（@bot_name + "冷场"关键词）
                    if self._bot_name and content.startswith(f"@{self._bot_name}") and "冷场" in content:
                        continue
                    return True
        except Exception as e:
            logger.error("查询回应失败: %s", e)
        return False

    def stop(self):
        """停止本用户的三个线程"""
        self._running = False
        try:
            self._queue.put(None)  # 唤醒处理线程退出
        except Exception:
            pass


class UserProcessorManager:
    """用户处理器注册表 — 懒创建（活跃用户）+ 预创建（破冰候选）"""

    def __init__(self):
        self._processors: dict[str, UserProcessor] = {}
        self._guard = threading.Lock()
        self._running = False
        self._sync_thread: threading.Thread | None = None

    def get_processor(self, user_id: str) -> UserProcessor:
        """获取用户处理器（懒创建，启动三个线程）"""
        with self._guard:
            p = self._processors.get(user_id)
            if p is None:
                p = UserProcessor(user_id)
                self._processors[user_id] = p
            return p

    def start(self):
        """启动管理器：预创建破冰候选 + 30min 同步循环（发现新候选）"""
        if self._running:
            return
        self._running = True
        self.sync_candidates()
        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._sync_thread.start()
        logger.info("用户处理器管理器已启动")

    def _sync_loop(self):
        while self._running:
            time.sleep(_SUMMARIZE_INTERVAL)
            try:
                self.sync_candidates()
            except Exception as e:
                logger.error("同步破冰候选异常: %s", e, exc_info=True)

    def sync_candidates(self):
        """预创建启用了破冰的用户处理器（冷场用户无消息也需常驻）"""
        try:
            url = cfg.get_service_url("db_services", "/api/user-configs/ice-breaker-candidates")
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return
            items = resp.json().get("items", [])
        except Exception as e:
            logger.error("获取破冰候选失败: %s", e)
            return
        created = 0
        for item in items:
            uid = item.get("user_id")
            if not uid:
                continue
            with self._guard:
                p = self._processors.get(uid)
                if p is None:
                    p = UserProcessor(uid)
                    self._processors[uid] = p
                    created += 1
            # 预填用户信息缓存（避免 tick 时补查）
            if item.get("wechat_name"):
                p._wechat_name = item["wechat_name"]
            if item.get("user_type"):
                p._user_type = item["user_type"]
        if items:
            logger.info("破冰候选同步: 新建 %d 个处理器 (共 %d)", created, len(self._processors))

    def summarize(self, user_id: str):
        """手动强制总结（strategy_mgmt 调用）"""
        self.get_processor(user_id).summarize(force=True, window=0)

    def generate_and_send(self, user_id: str, wechat_name: str, prompt: str = ""):
        """手动触发主动发言（trigger 路由调用）"""
        self.get_processor(user_id).generate_and_send(wechat_name, prompt)

    def stop(self):
        """停止所有用户处理器"""
        self._running = False
        with self._guard:
            procs = list(self._processors.values())
        for p in procs:
            p.stop()
        logger.info("用户处理器管理器已停止 (%d 个处理器)", len(procs))


# 全局单例
manager = UserProcessorManager()
