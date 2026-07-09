"""文档打印处理器 — 接收图片/文档文件，通过 CUPS 网络打印机输出"""
import os
import shutil
import tempfile
import logging
from . import BaseProcessor, registry
from src.common.schemas.agent_request import AgentRequest, ContentType
from src.common.lib.file_converter import FileConverter
from src.common.lib.file_recognize import FileRecognizer
from src.common.lib.image_binarize import ImageBinarrize
from src.common.lib.printer import Printer

logger = logging.getLogger(__name__)

SUPPORTED_EXT = {'.doc', '.docx', '.pdf', '.wps'}


class PrintProcessor(BaseProcessor):
    name = "print"
    description = "文档打印处理器"

    def priority(self) -> int:
        return 10

    def can_handle(self, req: AgentRequest) -> bool:
        # 文字命令
        if req.content_type == ContentType.TEXT:
            return True
        # 图片和文件
        if req.content_type in (ContentType.IMAGE, ContentType.FILE):
            return True
        return False

    def handle(self, req: AgentRequest, ctx) -> dict | None:
        printer = Printer()
        if not printer.is_ready:
            ctx.reply("打印机未就绪（请检查 PRINTER_NAME 配置）")
            return {"reply": "打印机未就绪"}

        # 文字命令处理
        if req.content_type == ContentType.TEXT:
            text = req.content.strip()
            if text == "开启照片打印功能":
                self._photograph_print = True
                ctx.reply("照片打印功能已开启")
                return {"reply": "照片打印功能已开启"}
            elif text == "关闭照片打印功能":
                self._photograph_print = False
                ctx.reply("照片打印功能已关闭")
                return {"reply": "照片打印功能已关闭"}
            return None  # 不处理其他文字

        # 文件/图片处理
        if not req.file_id:
            return None

        file_data = ctx.download_file(req.file_id)
        if not file_data:
            ctx.reply("下载文件失败")
            return {"reply": "下载文件失败"}

        tmpdir = tempfile.mkdtemp()
        try:
            # 猜测文件名和扩展名
            meta = req.metadata or {}
            file_name = meta.get("file_name", "print_file")
            file_path = os.path.join(tmpdir, file_name)
            with open(file_path, "wb") as f:
                f.write(file_data)

            converter = FileConverter()
            recognizer = FileRecognizer()
            ext = recognizer.get_extension(file_path)

            # 图片 → PDF → 打印
            if req.content_type == ContentType.IMAGE:
                binarizer = ImageBinarrize()
                binarized = os.path.join(tmpdir, "binarized_" + file_name)
                binarizer.process_image(file_path, binarized)
                pdf_path = converter.convert_image_to_pdf(binarized, tmpdir)
            elif ext in SUPPORTED_EXT and ext != ".pdf":
                pdf_path = converter.convert_document_to_pdf(file_path, tmpdir)
            elif ext == ".pdf":
                pdf_path = file_path
            else:
                ctx.reply(f"不支持的文件格式: {ext}")
                return {"reply": f"不支持的文件格式: {ext}"}

            success, job_id = printer.print_pdf(pdf_path)
            if success:
                ctx.reply(f"打印任务已创建: {job_id}")
                return {"reply": f"打印任务已创建: {job_id}"}
            ctx.reply(f"打印失败: {job_id}")
            return {"reply": f"打印失败: {job_id}"}

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


registry.register(PrintProcessor())
