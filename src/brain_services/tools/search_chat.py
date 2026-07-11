"""搜索历史聊天记录工具 — 让 LLM 能查询原始聊天数据"""
import json
import logging
import requests
from src.common.utils import cfg
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.search_chat")


class SearchChatHistoryTool(BaseTool):
    """搜索历史聊天记录"""

    def __init__(self):
        super().__init__(
            name="search_chat_history",
            description=(
                "搜索历史聊天记录，查找之前讨论过的内容。"
                "当用户问'我之前说过…'、'昨天…'、'上次你说…'、"
                "'之前那个xxx是什么'等涉及历史消息的问题时调用。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，如'买水果''南京东路''考试成绩'",
                    },
                    "hours_back": {
                        "type": "integer",
                        "description": "向前搜索的小时数，默认 72（3天内）",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最多返回条数，默认 10",
                    },
                },
                "required": ["keyword"],
            },
            silent=True,
        )

    def execute(self, args: dict) -> dict:
        keyword = args.get("keyword", "").strip()
        if not keyword:
            return {"text": "请提供搜索关键词", "files": []}

        hours_back = args.get("hours_back", 72)
        limit = min(args.get("limit", 10), 50)

        try:
            url = cfg.get_service_url("db_services", "/api/chat-messages/search")
            resp = requests.get(url, params={
                "keyword": keyword,
                "hours_back": hours_back,
                "limit": limit,
            }, timeout=15)

            if resp.status_code != 200:
                return {"text": f"搜索失败: {resp.status_code}", "files": []}

            data = resp.json()
            messages = data.get("messages", [])
            if not messages:
                return {"text": f"没找到包含「{keyword}」的历史消息", "files": []}

            lines = [f"找到 {data['total']} 条相关记录："]
            for m in messages:
                role = m.get("role", "?")
                content = (m.get("content") or "")[:200]
                time = (m.get("created_at") or "")[5:16]
                lines.append(f"[{time}] {role}: {content}")

            return {"text": "\n".join(lines), "files": []}

        except Exception as e:
            logger.error("搜索历史聊天失败: %s", e)
            return {"text": f"搜索失败: {e}", "files": []}


registry.register(SearchChatHistoryTool())
