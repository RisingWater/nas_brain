"""公众号链接保存处理器 — 将链接内容转为 DOCX 文件并发送"""
import os
import shutil
import tempfile
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

        tmpdir = tempfile.mkdtemp()
        try:
            converter = FixedWebConverter()
            docx_path = converter.convert_url_to_docx(url, tmpdir)

            if docx_path and os.path.exists(docx_path):
                ctx.reply("网页链接已转换为 DOCX，正在发送文件...")
                # 通过 wechat_gateway 发送文件
                with open(docx_path, "rb") as f:
                    file_data = f.read()
                who = req.metadata.get("wechat_name", "") or req.user_id
                ctx.send_wechat(who, None)  # placeholder
                # TODO: 发送文件到微信
                return {"reply": "链接已保存为 DOCX 文件"}
            ctx.reply("转换失败，请检查链接是否正确")
            return {"reply": "转换失败"}

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


registry.register(UrlSaveProcessor())
