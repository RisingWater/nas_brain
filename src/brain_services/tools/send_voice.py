"""发送语音消息工具 — 让 LLM 通过 voice_gateway 播放（带互斥锁）"""
import logging
import requests
from src.common.utils import cfg
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.send_voice")


class SendVoiceTool(BaseTool):
    """向语音系统发送消息播放请求"""

    def __init__(self):
        super().__init__(
            name="send_voice",
            description="通过语音播放一段文字。当你需要让 AI 说话时调用。",
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "要播放的文字内容",
                    },
                },
                "required": ["text"],
            },
            final=True,
        )

    def execute(self, args: dict) -> dict:
        text = args.get("text", "").strip()
        if not text:
            return {"text": "播放失败：缺少文字内容", "files": []}

        try:
            url = cfg.get_service_url("voice_gateway", "/api/voice/speak")
            resp = requests.post(url, json={"text": text}, timeout=60)
            data = resp.json()
            if data.get("code") == 200:
                logger.info("语音已播放: %.30s", text)
                return {"text": f"已播放语音: {text[:50]}", "files": []}
            return {"text": f"语音播放失败: {data.get('message')}", "files": []}
        except Exception as e:
            logger.error("语音播放失败: %s", e)
            return {"text": f"语音播放失败: {e}", "files": []}


registry.register(SendVoiceTool())
