"""策略引擎 — 消息分流 + smart/direct 处理"""
import os
import logging
import requests
from src.common.utils import cfg
from src.common.schemas.agent_request import AgentRequest, ProtocolType
from ..schema.brain_schema import AgentResponse
from ..processors import registry as proc_registry
from ..tools import registry as tool_registry
from ..status import ai_status
from .chat_recorder import ChatRecorder
from .context_builder import LLMContextBuilder
from .llm_handler import LLMHandler
from .tool_filter import ToolFilter

logger = logging.getLogger("brain_services.strategy.engine")

_WECHAT_BOT_NAME = os.getenv("WECHAT_BOT_NAME", "")


class StrategyEngine:
    """策略引擎 — 判断策略 + 分流处理"""

    def __init__(self):
        self.recorder = ChatRecorder()
        self.context_builder = LLMContextBuilder()
        self.llm_handler = LLMHandler()
        self.tool_filter = ToolFilter()

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
        }

    def is_mentioned(self, req: AgentRequest) -> bool:
        """检测群聊中是否 @ 了 Bot"""
        if not _WECHAT_BOT_NAME:
            return True  # 没配就不过滤
        content = req.content or ""
        return f"@{_WECHAT_BOT_NAME}" in content

    def should_skip(self, req: AgentRequest, config: dict) -> bool:
        """是否应该跳过处理（群聊 + group_at_only + 没 @）"""
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
        """主入口：判断策略 → 处理 → 返回"""
        # 0. 获取配置
        config = self.get_user_config(req.user_id)

        # 1. 先记录消息到 DB（即使后续跳过也要记录，供上下文使用）
        user_msg_id = self.recorder.record_user_message(req)

        # 2. 检查是否跳过（群聊无 @）
        if self.should_skip(req, config):
            return AgentResponse(data={
                "request_id": req.request_id,
                "text": "",
                "skipped": True,
            })

        # 3. Ignore 策略：只记录不处理
        strategy = self.get_strategy(req, config)
        if strategy == "ignore":
            logger.info("Ignore 策略，跳过处理: %.50s", req.content or "")
            return AgentResponse(data={
                "request_id": req.request_id,
                "text": "",
                "ignored": True,
            })

        # 4. 先尝试 processors
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
                    # 透传文件路径（由 agent route 统一发送到微信）
                    if "files" in result:
                        resp_data["files"] = result["files"]
                    return AgentResponse(data=resp_data)
            except Exception as e:
                logger.error("Processor %s 异常: %s", processor.name, e, exc_info=True)

        # 5. 按策略分流
        if strategy == "smart":
            return self._process_smart(req, config, user_msg_id)
        else:
            return self._process_direct(req)

    def _process_smart(self, req: AgentRequest, config: dict, user_msg_id: int | None = None) -> AgentResponse:
        """Smart 模式：LLM + 工具调用"""
        # 构建上下文
        sender = (req.metadata or {}).get("sender", "") if hasattr(req, 'metadata') else ""
        messages = self.context_builder.build(
            user_id=req.user_id,
            config=config,
            current_msg=req.content or "",
            protocol=req.protocol.value if hasattr(req.protocol, 'value') else str(req.protocol),
            chat_type=req.chat_type.value if hasattr(req.chat_type, 'value') else str(req.chat_type),
            exclude_msg_id=user_msg_id,
            sender=sender,
        )

        # 过滤工具
        all_tools = tool_registry.get_schemas()
        filtered_tools = self.tool_filter.filter(
            all_tools, config.get("allowed_tools"),
        )

        # 状态：思考中
        ai_status.set("thinking")

        # 执行 LLM 循环
        reply, files, req_tokens = self.llm_handler.handle(
            user_id=req.user_id,
            messages=messages,
            tools=filtered_tools,
            request_id=req.request_id,
        )
        # 记录本次请求的 token 用量到 metadata
        req.metadata["prompt_tokens"] = req_tokens.get("prompt_tokens", 0)
        req.metadata["completion_tokens"] = req_tokens.get("completion_tokens", 0)

        # __SKIP__：不回复，按 user_msg_id 删除该条消息
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
