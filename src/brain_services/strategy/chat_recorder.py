"""聊天记录器 — 通过 HTTP 调 db_services 写入 chat_messages"""
import json
import logging
import requests
from src.common.utils import cfg
from src.common.schemas.agent_request import AgentRequest

logger = logging.getLogger("brain_services.strategy.chat_recorder")


class ChatRecorder:
    """记录所有交互到 chat_messages 表"""

    def _url(self, path: str) -> str:
        return cfg.get_service_url("db_services", f"/api/chat-messages{path}")

    def record(self, user_id: str, role: str, *,
               content: str | None = None,
               tool_calls: list | None = None,
               tool_name: str | None = None,
               tool_result: dict | None = None,
               processor_name: str | None = None,
               protocol: str = "wechat",
               chat_type: str = "private",
               file_id: str | None = None,
               link_url: str | None = None,
               content_type: str | None = None,
               metadata: dict | None = None) -> int | None:
        """写入一条聊天记录"""
        meta = dict(metadata or {})
        if file_id:
            meta["file_id"] = file_id
        if link_url:
            meta["link_url"] = link_url
        if content_type:
            meta["content_type"] = content_type
        body = {
            "user_id": user_id,
            "role": role,
            "content": content,
            "tool_calls": tool_calls,
            "tool_name": tool_name,
            "tool_result": tool_result,
            "processor_name": processor_name,
            "protocol": protocol,
            "chat_type": chat_type,
            "metadata": meta,
        }
        try:
            resp = requests.post(self._url(""), json=body, timeout=10)
            data = resp.json()
            return data.get("id")
        except Exception as e:
            logger.error("记录聊天消息失败: %s", e)
            return None

    def record_batch(self, messages: list[dict]) -> list[int] | None:
        """批量写入聊天记录"""
        try:
            resp = requests.post(
                cfg.get_service_url("db_services", "/api/chat-messages/batch"),
                json={"messages": messages},
                timeout=15,
            )
            data = resp.json()
            return data.get("ids")
        except Exception as e:
            logger.error("批量记录聊天消息失败: %s", e)
            return None

    def record_user_message(self, req: AgentRequest) -> int | None:
        """记录用户消息（含附件信息）"""
        return self.record(
            user_id=req.user_id,
            role="user",
            content=str(req.content or ""),
            protocol=req.protocol.value if hasattr(req.protocol, 'value') else str(req.protocol),
            chat_type=req.chat_type.value if hasattr(req.chat_type, 'value') else str(req.chat_type),
            file_id=req.file_id,
            link_url=req.link_url,
            content_type=req.content_type.value if hasattr(req.content_type, 'value') else None,
            metadata=req.metadata,
        )

    def record_assistant(self, user_id: str, content: str,
                         tool_calls: list | None = None) -> int | None:
        """记录 LLM 回复"""
        return self.record(
            user_id=user_id, role="assistant",
            content=content, tool_calls=tool_calls,
        )

    def record_tool_result(self, user_id: str, tool_name: str,
                           tool_result: dict,
                           tool_call_id: str | None = None) -> int | None:
        """记录工具执行结果"""
        meta = {"tool_call_id": tool_call_id} if tool_call_id else {}
        return self.record(
            user_id=user_id, role="tool",
            tool_name=tool_name, tool_result=tool_result,
            metadata=meta,
        )

    def record_processor(self, req: AgentRequest, processor_name: str,
                         reply: str) -> int | None:
        """记录 processor 处理结果"""
        return self.record(
            user_id=req.user_id, role="processor",
            content=reply, processor_name=processor_name,
            protocol=req.protocol.value if hasattr(req.protocol, 'value') else str(req.protocol),
            chat_type=req.chat_type.value if hasattr(req.chat_type, 'value') else str(req.chat_type),
        )
