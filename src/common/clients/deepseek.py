"""DeepSeek API 客户端 — 对话/文本生成/Function Calling"""
import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

_API_URL = "https://api.deepseek.com/v1/chat/completions"


class DeepSeekAPI:
    """DeepSeek API 客户端"""

    def __init__(self):
        self._api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not self._api_key:
            logger.warning("DEEPSEEK_API_KEY 未设置")
        self.last_usage = {}  # 最近一次调用的 token 用量

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    def ask_single_question(self, prompt: str, model: str = "deepseek-v4-flash", timeout: int = 60) -> str | None:
        """单轮问答（无上下文，保留给简单场景使用）"""
        result = self.chat(messages=[{"role": "user", "content": prompt}], model=model, timeout=timeout)
        return result.get("content") if result else None

    def chat(self, messages: list[dict], model: str = "deepseek-v4-flash",
             timeout: int = 60) -> dict | None:
        """通用对话，返回完整响应中的 message 字段"""
        result = self._request(messages=messages, model=model, timeout=timeout)
        if result:
            return result.get("choices", [{}])[0].get("message")
        return None

    def chat_with_tools(self, messages: list[dict], tools: list[dict] | None = None,
                        model: str = "deepseek-v4-flash", timeout: int = 120) -> dict | None:
        """支持 Function Calling 的对话

        返回 message 字典，包含 content 和/或 tool_calls。
        tool_calls 格式：
        [{"id": "call_xxx", "type": "function",
          "function": {"name": "tool_name", "arguments": '{"arg":"val"}'}}]
        """
        body = {"messages": messages, "model": model}
        if tools:
            body["tools"] = tools
        result = self._request(**body, timeout=timeout)
        if result:
            return result.get("choices", [{}])[0].get("message")
        return None

    def _request(self, **kwargs) -> dict | None:
        """底层请求封装"""
        if not self._api_key:
            logger.error("DeepSeek API key 未配置")
            return None
        kwargs.setdefault("stream", False)
        try:
            resp = requests.post(
                _API_URL,
                headers=self._headers(),
                json=kwargs,
                timeout=kwargs.get("timeout", 60),
            )
            if resp.status_code == 200:
                data = resp.json()
                self.last_usage = data.get("usage", {})
                return data
            logger.error("DeepSeek API 错误: %s - %s", resp.status_code, resp.text)
        except Exception as e:
            logger.error("DeepSeek API 调用失败: %s", e)
        return None
