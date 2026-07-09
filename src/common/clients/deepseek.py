"""DeepSeek API 客户端 — 对话/文本生成"""
import os
import logging
import requests

logger = logging.getLogger(__name__)


class DeepSeekAPI:
    """DeepSeek API 客户端"""

    def __init__(self):
        self._api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not self._api_key:
            logger.warning("DEEPSEEK_API_KEY 未设置")

    def ask_single_question(self, prompt: str, model: str = "deepseek-v4-flash", timeout: int = 60) -> str | None:
        if not self._api_key:
            logger.error("DeepSeek API key 未配置")
            return None
        try:
            resp = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False},
                timeout=timeout,
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                return content
            logger.error("DeepSeek API 错误: %s - %s", resp.status_code, resp.text)
        except Exception as e:
            logger.error("DeepSeek API 调用失败: %s", e)
        return None
