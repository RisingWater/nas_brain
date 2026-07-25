"""冰点引擎 — 群聊冷场时 AI 主动发言

后台线程定期检查启用了冰点的群聊，冷场超时后用 LLM 生成消息并发送。
"""
import os
import uuid
import time
import random
import logging
import threading
import requests
from datetime import datetime
from src.common.utils import cfg
from .strategy.context_builder import LLMContextBuilder
from .strategy.llm_handler import LLMHandler

logger = logging.getLogger("brain_services.ice_breaker")


def _send_wechat(who: str, text: str):
    """通过 wechat_gateway 发送文本消息"""
    try:
        url = cfg.get_service_url("wechat_gateway", "/api/gateway/send-text")
        resp = requests.post(url, json={"who": who, "msg": text}, timeout=10)
        if resp.status_code == 200:
            logger.info("冰点已发送到 %s: %.50s", who, text)
        else:
            logger.warning("冰点发送失败: %s", resp.text)
    except Exception as e:
        logger.error("冰点发送异常: %s", e)


class IceBreakerEngine:
    """冰点引擎 — 后台线程定期检查群聊冷场并主动发言"""

    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None
        self._state: dict[str, dict] = {}
        self.context_builder = LLMContextBuilder()
        self.llm_handler = LLMHandler()
        self._bot_name = os.getenv("WECHAT_BOT_NAME", "")

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("冰点引擎已启动，检查间隔=30~40分钟")

    def stop(self):
        self._running = False

    def _run_loop(self):
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.error("冰点引擎异常: %s", e, exc_info=True)
            # 随机休眠 30~40 分钟（基础30min + 随机5~10min）
            jitter = random.randint(300, 600)
            time.sleep(1800 + jitter)

    def _tick(self):
        """一次检查循环：获取候选群 → 逐群检查"""
        try:
            url = cfg.get_service_url("db_services", "/api/user-configs/ice-breaker-candidates")
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return
            candidates = resp.json().get("items", [])
        except Exception as e:
            logger.error("获取冰点候选群失败: %s", e)
            return

        if not candidates:
            return

        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        for group in candidates:
            try:
                self._check_group(group, now, today)
            except Exception as e:
                logger.error("检查群 %s 异常: %s", group.get("user_id", "?"), e, exc_info=True)

    def _is_night_mode(self, config: dict, now: datetime) -> bool:
        """检查当前时间是否在免打扰时段内"""
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

    def _check_group(self, group: dict, now: datetime, today: str):
        """检查单个群是否需要冰点"""
        user_id = group["user_id"]
        config = group
        wechat_name = config.get("wechat_name", "")

        if not wechat_name:
            try:
                url = cfg.get_service_url("db_services", f"/api/users/{user_id}")
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    wechat_name = resp.json().get("wechat_name", "")
            except Exception:
                pass
            if not wechat_name:
                logger.warning("群 %s 无 wechat_name，跳过", user_id)
                return

        # 1. 夜间模式
        if self._is_night_mode(config, now):
            return

        state = self._state.setdefault(user_id, {
            "last_proactive_time": time.time(),
            "msg_id_at_send": 0,
            "attempt_date": "",
        })

        # 2. 当天已尝试且无人回应 → 跳过
        if state["attempt_date"] == today:
            return

        # 3. 获取最新消息时间
        latest = self._get_latest_message(user_id)
        if not latest:
            return

        latest_time_str = latest.get("created_at", "")
        try:
            latest_time = datetime.strptime(latest_time_str, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return

        # 4. 冷场检查
        trigger_minutes = config.get("ice_breaker_trigger_minutes", 15)
        if (now - latest_time).total_seconds() < trigger_minutes * 60:
            return

        # 5. 冷却检查
        cooldown_minutes = config.get("ice_breaker_cooldown_minutes", 60)
        if time.time() - state["last_proactive_time"] < cooldown_minutes * 60:
            return

        # 6. 上次冰点后是否有人回应
        if state["msg_id_at_send"] and state["attempt_date"]:
            if not self._has_user_response(user_id, state["msg_id_at_send"]):
                state["attempt_date"] = today
                logger.info("群 %s 上次冰点无人回应，今日跳过", wechat_name)
                return
            # 有人回应 → 重置
            state["msg_id_at_send"] = 0
            state["attempt_date"] = ""

        # 7. 发送冰点！
        logger.info("冰点触发: %s (静默 %.1f 分钟)", wechat_name, (now - latest_time).total_seconds() / 60)
        self._generate_and_send(user_id, wechat_name, config, latest)

        state["last_proactive_time"] = time.time()
        state["msg_id_at_send"] = latest.get("id", 0)
        state["attempt_date"] = today

    def _get_latest_message(self, user_id: str) -> dict | None:
        """查询群聊最新一条消息"""
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
        """检查 since_id 之后是否有真实的用户消息（排除冰点触发消息）"""
        try:
            url = cfg.get_service_url("db_services", f"/api/chat-messages/{user_id}")
            resp = requests.get(url, params={"since_id": since_id, "limit": 50}, timeout=10)
            if resp.status_code == 200:
                msgs = resp.json().get("messages", [])
                for msg in msgs:
                    if msg.get("role") != "user":
                        continue
                    content = (msg.get("content") or "").strip()
                    # 跳过冰点触发消息（@bot_name + "冷场"关键词）
                    if self._bot_name and content.startswith(f"@{self._bot_name}") and "冷场" in content:
                        continue
                    return True
        except Exception as e:
            logger.error("查询回应失败: %s", e)
        return False

    def generate_and_send(self, user_id: str, wechat_name: str, prompt_override: str = ""):
        """公开接口：立即生成并发送主动发言（测试用）"""
        config = {"ice_breaker_prompt": prompt_override} if prompt_override else {}
        if not config.get("ice_breaker_prompt"):
            try:
                url = cfg.get_service_url("db_services", f"/api/user-configs/{user_id}")
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    config = resp.json()
            except Exception:
                pass
        # 查 user_type
        if not config.get("user_type"):
            try:
                url = cfg.get_service_url("db_services", f"/api/users/{user_id}")
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    config["user_type"] = resp.json().get("user_type") or "person"
            except Exception:
                pass
        self._generate_and_send(user_id, wechat_name, config, {})

    def _generate_and_send(self, user_id: str, wechat_name: str, config: dict, latest_msg: dict):
        """用 LLM 生成主动发言消息并发送"""
        try:
            # 保证有 system_prompt（candidates 端点通常带，测试入口可能缺）
            if not config.get("system_prompt"):
                try:
                    url = cfg.get_service_url("db_services", f"/api/user-configs/{user_id}")
                    resp = requests.get(url, timeout=10)
                    if resp.status_code == 200:
                        full = resp.json()
                        config["system_prompt"] = full.get("system_prompt", "")
                except Exception:
                    pass

            user_type = config.get("user_type", "person")

            # 确定触发语：ice_breaker_prompt 用户可自定义，空则用默认
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

            # 构建上下文（含三层记忆 + 近期聊天）
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
                _send_wechat(wechat_name, reply.strip())
            else:
                logger.warning("主动发言回复为空，%s", user_id)

        except Exception as e:
            logger.error("主动发言生成/发送失败 %s: %s", user_id, e, exc_info=True)


# 全局单例
ice_breaker_engine = IceBreakerEngine()
