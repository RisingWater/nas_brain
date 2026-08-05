"""策略引擎 — 消息分流 + smart/direct 处理"""
import os
import logging
import requests
from src.common.utils import cfg
from src.common.schemas.agent_request import AgentRequest, ContentType, ProtocolType
from ..schema.brain_schema import AgentResponse
from ..processors import registry as proc_registry
from ..tools import registry as tool_registry
from ..status import ai_status
from .chat_recorder import ChatRecorder
from .context_builder import LLMContextBuilder
from .llm_handler import LLMHandler
from .tool_filter import ToolFilter
from src.common.lib.pity_rate import PityRate

logger = logging.getLogger("brain_services.strategy.engine")

_WECHAT_BOT_NAME = os.getenv("WECHAT_BOT_NAME", "")


class StrategyEngine:
    """策略引擎 — 判断策略 + 分流处理"""

    def __init__(self):
        self.recorder = ChatRecorder()
        self.context_builder = LLMContextBuilder()
        self.llm_handler = LLMHandler()
        self.tool_filter = ToolFilter()
        # 表情包保底概率，按用户各持一个实例（配置的概率变化时自动重建）
        self._bqb_pity: dict[str, PityRate] = {}

    def get_user_config(self, user_id: str) -> dict:
        """获取用户配置（不存在则返回默认值）"""
        try:
            url = cfg.get_service_url("db_services", f"/api/user-configs/{user_id}")
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error("获取用户配置失败: %s", e)
        return {
            "strategy": "smart",
            "system_prompt": "",
            "allowed_tools": None,
            "short_term_window": 30,
            "group_at_only": True,
            "batch_enabled": False,
            "group_members": [],
        }

    def is_mentioned(self, req: AgentRequest) -> bool:
        """检测群聊中是否 @ 了 Bot"""
        if not _WECHAT_BOT_NAME:
            return True  # 没配就不过滤
        content = req.content or ""
        return f"@{_WECHAT_BOT_NAME}" in content

    def should_skip(self, req: AgentRequest, config: dict) -> bool:
        """是否应该跳过处理（群聊 + group_at_only + 没 @）"""
        # 非文字消息（图片/文件/链接/视频）无法 @，不跳过
        if req.content_type != ContentType.TEXT:
            return False
        if req.chat_type.value != "group":
            return False
        if not config.get("group_at_only", True):
            return False
        if self.is_mentioned(req):
            return False
        logger.info("群消息无 @，跳过处理: %.50s", req.content or "")
        return True

    def get_strategy(self, req: AgentRequest, config: dict) -> str:
        """判断策略：voice 强制 smart，其他按配置"""
        if req.protocol == ProtocolType.VOICE:
            return "smart"
        return config.get("strategy", "smart")

    def process(self, req: AgentRequest) -> AgentResponse:
        """完整单条链路：获取配置 → 记录消息 → 跳过判断 → 策略分流

        覆盖 smart（含 IMAGE OCR）/ direct（processor）/ ignore 全部分支。
        """
        config = self.get_user_config(req.user_id)
        user_msg_id = self.recorder.record_user_message(req)

        # 检查是否跳过（群聊无 @）
        if self.should_skip(req, config):
            return AgentResponse(data={
                "request_id": req.request_id,
                "text": "",
                "skipped": True,
            })

        # 获取策略（voice 强制 smart）
        strategy = self.get_strategy(req, config)
        if strategy == "ignore":
            logger.info("Ignore 策略，跳过处理: %.50s", req.content or "")
            return AgentResponse(data={
                "request_id": req.request_id,
                "text": "",
                "ignored": True,
            })

        # smart：IMAGE + ocr_image 配置 → OCR 识别，存历史，不回复
        if strategy == "smart":
            if req.content_type == ContentType.IMAGE and req.file_id and config.get("ocr_image"):
                ocr_text = self._ocr_image(req)
                if ocr_text:
                    updated = f"{req.content or ''}\n【OCR识别结果】\n{ocr_text}"
                    self.recorder.update_content(user_msg_id, updated)
                    logger.info("图片 OCR 完成，跳过回复: %.50s", ocr_text)
                else:
                    logger.info("图片 OCR 无结果，跳过回复")
                return AgentResponse(data={
                    "request_id": req.request_id,
                    "text": "",
                    "skipped": True,
                })
            return self._process_smart(req, config, user_msg_id)

        # direct：processor 优先，无命中则简单兜底
        processor, ctx = proc_registry.find_handler(req)
        if processor:
            logger.info("Processor %s 处理请求", processor.name)
            try:
                result = processor.handle(req, ctx)
                if result and "reply" in result:
                    self.recorder.record_processor(req, processor.name, result["reply"])
                    resp_data = {
                        "request_id": req.request_id,
                        "text": result["reply"],
                        "processor": processor.name,
                    }
                    if "files" in result:
                        resp_data["files"] = result["files"]
                    return AgentResponse(data=resp_data)
            except Exception as e:
                logger.error("Processor %s 异常: %s", processor.name, e, exc_info=True)
        return self._process_direct(req)

    def process_batch(self, reqs: list[AgentRequest], config: dict) -> dict:
        """批量链路（smart + wechat 批次，与 process() 单条链路完全独立）

        流程：逐条记录 → 图片 OCR 转文字 → 按 @ 模式分组 → 文字消息合并成
        一个提示词一次 LLM。合并的纯文字消息在构建上下文时排除（避免重复）；
        图片消息内容（含 OCR 结果，已写入聊天记录）保留在上下文中由
        context_builder 注入。

        两种配置：
        - group_at_only=True（群聊只回复 @）：抽取 @ 消息构建提示词，
          非 @ 消息只记录（skip 不回复）
        - group_at_only=False（答复所有消息）：全部可答复消息
          （文字 + OCR 成功的图片）合并成一个提示词

        Returns:
            {"resp": AgentResponse | None,   # None = 无可处理消息（全部跳过）
             "actionable": [(req, msg_id)],  # 参与合并的消息（第一条为主请求）
             "skipped": [(req, msg_id)]}     # 只记录不回复的消息
        """
        user_id = reqs[0].user_id
        is_group = reqs[0].chat_type.value == "group"
        group_at_only = config.get("group_at_only", True)

        # 1. 逐条记录 + 图片先 OCR（smart 模式图片本质是转文字处理）
        items = []  # (req, msg_id, ocr_text)
        for req in reqs:
            msg_id = self.recorder.record_user_message(req)
            ocr_text = ""
            if (req.content_type == ContentType.IMAGE and req.file_id
                    and config.get("ocr_image")):
                ocr_text = self._ocr_image(req) or ""
                if ocr_text:
                    updated = f"{req.content or ''}\n【OCR识别结果】\n{ocr_text}"
                    self.recorder.update_content(msg_id, updated)
            items.append((req, msg_id, ocr_text))

        # 2. 分组：@ 模式只取 @ 消息；否则全部可答复消息
        if is_group and group_at_only:
            actionable = [it for it in items if self.is_mentioned(it[0])]
        else:
            actionable = [it for it in items
                          if it[0].content_type == ContentType.TEXT or it[2]]
        skipped = [it for it in items if it not in actionable]
        if not actionable:
            return {"resp": None, "actionable": [], "skipped": skipped}

        # 3. 全部合并成一个提示词（N>=1，1 条等价单条）
        #    图片消息不拼进提示词：OCR 结果已在第 1 步写入聊天记录，
        #    由 context_builder 作为历史消息注入上下文（因此也不排除）
        lines = []
        exclude_ids = []
        for req, mid, ocr_text in actionable:
            if ocr_text:
                continue  # 图片消息：内容走聊天记录，不参与合并
            sender = (req.metadata or {}).get("sender", "") if hasattr(req, "metadata") else ""
            content = req.content or ""
            if is_group and sender:
                lines.append(f"{sender}: {content}")
            elif is_group:
                # 兜底：群聊 sender 缺失（备注为空）时也标明来源
                lines.append(f"群友: {content}")
            else:
                lines.append(content)
            if mid:
                exclude_ids.append(mid)
        if not lines:
            # 批内没有可合并的文字（全是图片）→ 全部跳过不回复，
            # 与单条链路"图片 OCR 后 skip"行为一致（OCR 结果已写入聊天记录）
            logger.info("用户 %s 批内无可合并文字，全部跳过 (%d 条)",
                        user_id, len(items))
            return {"resp": None, "actionable": [], "skipped": items}
        first, _fmid, _ocr = actionable[0]
        merged_content = "\n".join(lines)
        logger.info("用户 %s 合并处理 %d 条消息 (@模式=%s)",
                    user_id, len(actionable), group_at_only)
        logger.info("合并 content: %s", merged_content)

        resp = self._process_smart(first, config, user_msg_id=None,
                                   exclude_msg_ids=exclude_ids or None,
                                   content_override=merged_content)
        return {"resp": resp, "actionable": actionable, "skipped": skipped}

    def _process_smart(self, req: AgentRequest, config: dict,
                       user_msg_id: int | None = None,
                       exclude_msg_ids: list[int] | None = None,
                       content_override: str | None = None) -> AgentResponse:
        """Smart 模式：LLM + 工具调用

        Args:
            content_override: 合并文本（多条文字消息拼成一条 user 消息，已带 sender 前缀）
            exclude_msg_ids: 排除的原始消息 ID（内容已并入提示词的批内文字消息，
                避免上下文重复；图片消息靠聊天记录注入，不在此列）
        """
        # 非文字消息（无 processor 处理的情况下）LLM 无法处理，直接跳过；
        # 合并模式 content_override 已是文本（图片已 OCR 转文字），不检查
        if content_override is None and req.content_type != ContentType.TEXT:
            logger.info("非文字消息跳过 LLM: content_type=%s", req.content_type.value)
            return AgentResponse(data={
                "request_id": req.request_id,
                "text": "",
                "skipped": True,
            })

        # 合并模式用合并文本作为当前消息；单条用原内容
        current_msg = content_override if content_override is not None else (req.content or "")
        exclude_ids = exclude_msg_ids if exclude_msg_ids is not None else (
            [user_msg_id] if user_msg_id else None)

        # 构建上下文（合并文本已带 sender 前缀，不再重复加）
        sender = (req.metadata or {}).get("sender", "") if hasattr(req, 'metadata') else ""
        messages = self.context_builder.build(
            user_id=req.user_id,
            config=config,
            current_msg=current_msg,
            protocol=req.protocol.value if hasattr(req.protocol, 'value') else str(req.protocol),
            chat_type=req.chat_type.value if hasattr(req.chat_type, 'value') else str(req.chat_type),
            exclude_msg_ids=exclude_ids,
            sender=sender if content_override is None else "",
        )

        # 过滤工具
        all_tools = tool_registry.get_schemas()
        filtered_tools = self.tool_filter.filter(
            all_tools, config.get("allowed_tools"),
        )

        # 状态：思考中（agent.py 已设，此处确保有内容）
        ai_status.set("thinking", message=current_msg[:80])

        # 执行 LLM 循环
        # 仅语音启用 final 属性（VAD 收录短 + TTS 慢，延迟敏感）；
        # 微信/Web 禁用（多工具场景伪造响应容易出错，且无 TTS 不敏感）
        reply, files, req_tokens = self.llm_handler.handle(
            user_id=req.user_id,
            messages=messages,
            tools=filtered_tools,
            request_id=req.request_id,
            final_enabled=req.protocol == ProtocolType.VOICE,
        )
        # 记录本次请求的 token 用量到 metadata
        req.metadata["prompt_tokens"] = req_tokens.get("prompt_tokens", 0)
        req.metadata["completion_tokens"] = req_tokens.get("completion_tokens", 0)

        # __SKIP__：不回复，按 user_msg_id 删除该条消息（仅单条路径；
        # 合并模式 user_msg_id=None，批内是他人真实消息，不删除）
        if reply and reply.strip() == "__SKIP__":
            logger.info("LLM 返回 __SKIP__，跳过并删除消息 msg_id=%s", user_msg_id)
            if user_msg_id:
                try:
                    import requests as _req
                    url = cfg.get_service_url("db_services", f"/api/chat-messages/single/{user_msg_id}")
                    _req.delete(url, timeout=5)
                except Exception as e:
                    logger.warning("删除 SKIP 消息失败: %s", e)
            return AgentResponse(data={
                "request_id": req.request_id,
                "text": "",
                "skipped": True,
            })

        # 表情包：微信 smart 模式下，按保底概率附带一张梗图
        # 配置的 bqb_probability 是数学期望，PityRate 自动求解初始概率保证长期期望一致
        if reply and reply.strip() not in ("__SKIP__", "") and config.get("send_bqb"):
            if req.protocol == ProtocolType.WECHAT:
                target_prob = config.get("bqb_probability", 50) / 100
                pity = self._bqb_pity.get(req.user_id)
                if pity is None or abs(pity.target_prob - target_prob) > 1e-6:
                    pity = PityRate(target_prob)
                    self._bqb_pity[req.user_id] = pity
                if pity.roll():
                    bqb_path = self._attach_bqb(reply)
                    if bqb_path:
                        if files is None:
                            files = []
                        elif isinstance(files, tuple):
                            files = list(files)
                        files.append(bqb_path)

        return AgentResponse(data={
            "request_id": req.request_id,
            "text": reply or "（无回复）",
            "files": files,
        })

    def _process_direct(self, req: AgentRequest) -> AgentResponse:
        """Direct 模式：processor 未命中时的简单回复"""
        return AgentResponse(data={
            "request_id": req.request_id,
            "text": f"已收到你的消息：{req.content or ''}",
            "received": True,
        })

    def _ocr_image(self, req: AgentRequest) -> str | None:
        """下载图片并 OCR，返回识别文本"""
        import shutil
        import tempfile
        import requests as _req
        from src.common.utils import cfg as _cfg
        from src.common.utils.tracer import trace_event

        trace_event(req.request_id, "ocr_start", protocol=req.protocol.value, user_id=req.user_id)
        try:
            dl_url = _cfg.get_service_url("wechat_gateway", f"/api/gateway/files/{req.file_id}/download")
            resp = _req.get(dl_url, timeout=30)
            if resp.status_code != 200:
                logger.warning("OCR 下载图片失败: HTTP %s", resp.status_code)
                return None
        except Exception as e:
            logger.warning("OCR 下载图片异常: %s", e)
            return None

        tmpdir = tempfile.mkdtemp()
        try:
            img_path = os.path.join(tmpdir, "ocr_input.png")
            with open(img_path, "wb") as f:
                f.write(resp.content)

            from src.common.lib.paddle_ocr import PaddleOCR, layout_ocr_text
            ocr = PaddleOCR()
            result = ocr.recognize(img_path)
            logger.info("OCR 结果: success=%s text=%.100s items=%d", result.get("success"), result.get("text","")[:100], len(result.get("items", [])))
            if result["success"]:
                # 优先用坐标重排版面（保留视觉布局，避免 LLM 错误组合相邻字段），
                # 无坐标时回退到服务端拼接的 text
                ocr_text = layout_ocr_text(result.get("items")) or result.get("text", "")
                if ocr_text:
                    logger.info("OCR 识别完成: %.50s", ocr_text)
                    return ocr_text
            logger.info("OCR 未识别到文字")
            return None
        except Exception as e:
            logger.warning("OCR 处理异常: %s", e)
            return None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _attach_bqb(self, reply: str) -> str | None:
        """根据回复内容生成表情包关键词，只取最后一个搜索（单次 API 调用）"""
        try:
            from src.common.clients.deepseek import DeepSeekAPI
            deepseek = DeepSeekAPI()
            raw = deepseek.ask_single_question(
                f"根据以下回复内容，生成3个表情包搜索关键词，从抽象到简单，最后一个必须只有2个字。"
                f"用中文逗号分隔，只返回关键词不要其他文字：\n{reply[:200]}"
            )
            if not raw:
                return None
            keywords = [kw.strip().strip('"\'').strip() for kw in raw.replace("，", ",").split(",") if kw.strip()]
            keywords = [kw for kw in keywords if 2 <= len(kw) <= 8]
            if not keywords:
                logger.warning("BQB 关键词列表无效: %s", raw)
                return None
            logger.info("BQB 关键词: %s ← %s", keywords, reply[:30])

            from src.common.lib.bqb_generator import get_random_bqb
            for kw in keywords:
                path = get_random_bqb(kw)
                if path:
                    return path
            return None
        except Exception as e:
            logger.warning("BQB 生成失败: %s", e)
            return None
