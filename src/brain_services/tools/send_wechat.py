"""发送微信消息工具 — 让 LLM 主动向指定用户发送微信"""
import logging
import requests
from src.common.utils import cfg
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.send_wechat")


class SendWechatTool(BaseTool):
    """发送微信消息给指定用户"""

    def __init__(self):
        super().__init__(
            name="send_wechat",
            description="向指定微信用户或群发送消息。当你需要主动推送信息时调用。",
            parameters={
                "type": "object",
                "properties": {
                    "who": {
                        "type": "string",
                        "description": "接收人微信名或群名",
                    },
                    "msg": {
                        "type": "string",
                        "description": "要发送的消息内容",
                    },
                },
                "required": ["who", "msg"],
            },
            final=True,
        )

    def execute(self, args: dict) -> dict:
        who = args.get("who", "").strip()
        msg = args.get("msg", "").strip()
        if not who or not msg:
            return {"text": "发送失败：缺少接收人或消息内容", "files": []}

        try:
            url = cfg.get_service_url("wechat_gateway", "/api/gateway/send-text")
            resp = requests.post(url, json={"who": who, "msg": msg}, timeout=10)
            data = resp.json()
            if data.get("code") == 200:
                logger.info("微信消息已发送 -> %s: %.30s", who, msg)
                return {"text": f"消息已发送给 {who}", "files": []}
            return {"text": f"发送失败: {data.get('message')}", "files": []}
        except Exception as e:
            logger.error("发送微信消息失败: %s", e)
            return {"text": f"发送失败: {e}", "files": []}


registry.register(SendWechatTool())
