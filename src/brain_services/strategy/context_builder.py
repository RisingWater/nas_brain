"""LLM 上下文构建器 — 组装三层记忆 + system prompt"""
import os
import logging
import requests
from src.common.utils import cfg

logger = logging.getLogger("brain_services.strategy.context_builder")

_MEMORY_FILE = os.getenv("MEMORY_FILE", "data/memory.md")
_BOT_NAME = os.getenv("BOT_NAME", "NAS Brain")
_DEFAULT_SYSTEM_PROMPT = f"你是 {_BOT_NAME}，一个智能助手。请用中文回答用户的问题。"


def _read_long_term_memory() -> str:
    """读取长期记忆（memory.md）"""
    if not os.path.exists(_MEMORY_FILE):
        return ""
    try:
        with open(_MEMORY_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logger.error("读取长期记忆失败: %s", e)
        return ""


class LLMContextBuilder:
    """按时间段构建 LLM 上下文：system + 长期 + 中期 + 短期 + 当前消息"""

    def build(self, user_id: str, config: dict, current_msg: str,
              protocol: str = "wechat", chat_type: str = "private") -> list[dict]:
        """构建 OpenAI-format messages 列表"""
        messages = []

        # 1. System prompt
        system_prompt = (config.get("system_prompt", "") or "").strip()
        if not system_prompt:
            system_prompt = _DEFAULT_SYSTEM_PROMPT
        messages.append({"role": "system", "content": system_prompt})

        # 2. Long-term memory (memory.md)
        long_term = _read_long_term_memory()
        if long_term:
            messages.append({
                "role": "system",
                "content": f"【长期记忆】\n{long_term}\n（以上是长期记忆，由你维护的事实列表）",
            })

        # 3. Mid-term memory (chat_summaries)
        mid_term = self._get_mid_term_summary(user_id)
        if mid_term:
            messages.append({
                "role": "system",
                "content": f"【历史对话总结】\n{mid_term}",
            })

        # 4. Short-term memory (recent chat_messages)
        window_minutes = config.get("short_term_window", 30)
        short_term = self._get_short_term_history(user_id, window_minutes)
        for msg in short_term:
            messages.append(msg)

        # 5. Current user message
        messages.append({"role": "user", "content": current_msg})

        return messages

    def _get_mid_term_summary(self, user_id: str) -> str | None:
        """获取中期记忆总结"""
        try:
            url = cfg.get_service_url("db_services", f"/api/chat-summaries/{user_id}/latest")
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("summary")
        except Exception:
            pass
        return None

    def _get_short_term_history(self, user_id: str, window_minutes: int) -> list[dict]:
        """获取短期记忆（最近 N 分钟内的消息）"""
        try:
            url = cfg.get_service_url("db_services", f"/api/chat-messages/{user_id}")
            # 用 since_time 做时间过滤
            import datetime
            since = (datetime.datetime.utcnow() - datetime.timedelta(minutes=window_minutes))
            resp = requests.get(url, params={
                "limit": 200,
                "since_time": since.strftime("%Y-%m-%d %H:%M:%S"),
            }, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                result = []
                for msg in data.get("messages", []):
                    role = msg.get("role", "")
                    if role in ("user", "assistant"):
                        result.append({
                            "role": role,
                            "content": msg.get("content") or "",
                        })
                    elif role == "tool":
                        result.append({
                            "role": "tool",
                            "content": f"工具 {msg.get('tool_name')} 返回: {msg.get('tool_result', {})}",
                            "tool_call_id": msg.get("id"),
                        })
                    elif role == "processor":
                        result.append({
                            "role": "assistant",
                            "content": f"[处理器 {msg.get('processor_name')}]: {msg.get('content')}",
                        })
                return result
        except Exception as e:
            logger.error("获取短期记忆失败: %s", e)
        return []
