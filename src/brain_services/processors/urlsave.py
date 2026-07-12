"""公众号链接保存处理器 — 将链接内容转为 DOCX 文件"""
import os
import logging
from . import BaseProcessor, registry
from src.common.schemas.agent_request import AgentRequest, ContentType
from src.common.lib.fixed_web_converter import FixedWebConverter

logger = logging.getLogger(__name__)


class UrlSaveProcessor(BaseProcessor):
    name = "urlsave"
    description = "公众号链接保存处理器"

    def priority(self) -> int:
        return 10

    def can_handle(self, req: AgentRequest) -> bool:
        return req.content_type == ContentType.LINK and bool(req.link_url)

    def handle(self, req: AgentRequest, ctx) -> dict | None:
        url = req.link_url
        if not url:
            return None

        ctx.reply("正在转换网页链接，请稍候...")

        temp_dir = os.getenv("TEMP_DIR", "data")
        os.makedirs(temp_dir, exist_ok=True)
        try:
            converter = FixedWebConverter()
            docx_path = converter.convert_url_to_docx(url, temp_dir)

            if docx_path and os.path.exists(docx_path):
                ctx.reply("网页链接已转换为 DOCX，正在发送文件...")
                # 返回文件路径，由 agent route 统一发送到微信
                return {"reply": "链接已保存为 DOCX 文件", "files": [docx_path]}
            ctx.reply("转换失败，请检查链接是否正确")
            return {"reply": "转换失败"}

        except Exception as e:
            logger.error("转换失败: %s", e, exc_info=True)
            ctx.reply(f"转换失败: {e}")
            return {"reply": f"转换失败: {e}"}


registry.register(UrlSaveProcessor())
