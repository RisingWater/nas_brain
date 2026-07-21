"""文件读写工具 — 在 TEMP_DIR 内读写文件，支持 txt/pdf"""
import os
import logging
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.write_file")

_TEMP_DIR = os.path.normpath(os.getenv("TEMP_DIR", "data"))

# PDF 写入支持（可选依赖 fpdf2）
_HAS_FPDF = False
try:
    from fpdf import FPDF
    _HAS_FPDF = True
except ImportError:
    pass

# PDF 读取支持（可选依赖 pypdf / PyPDF2）
_HAS_PDF_READ = False
_READER = None
for _mod in ["pypdf", "PyPDF2"]:
    try:
        _READER = __import__(_mod, fromlist=["PdfReader"])
        _HAS_PDF_READ = True
        break
    except ImportError:
        continue


def _safe_path(filename: str) -> str:
    """确保文件路径在 TEMP_DIR 内，防止路径穿越"""
    os.makedirs(_TEMP_DIR, exist_ok=True)
    full = os.path.normpath(os.path.join(_TEMP_DIR, os.path.basename(filename)))
    if not full.startswith(_TEMP_DIR):
        raise ValueError("不允许访问 TEMP_DIR 以外的文件")
    return full


class WriteTextFileTool(BaseTool):
    """将文本保存为 txt 文件"""

    def __init__(self):
        super().__init__(
            name="write_text_file",
            display_name="写文本文件",
            description="将文本内容保存为 txt 文件。可用于保存报告、清单、摘要等较长的文本，文件会通过微信发送给用户。",
            parameters={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "文件内容",
                    },
                    "filename": {
                        "type": "string",
                        "description": "文件名，如'成绩单.txt'，默认自动生成",
                    },
                },
                "required": ["content"],
            },
            final=True,
        )

    def execute(self, args: dict) -> dict:
        content = args.get("content", "").strip()
        if not content:
            return {"text": "内容为空", "files": []}

        filename = args.get("filename", "").strip()
        if not filename:
            filename = f"output_{os.urandom(4).hex()}.txt"
        if not filename.endswith(".txt"):
            filename += ".txt"

        try:
            filepath = _safe_path(filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("文本文件已保存: %s (%d 字)", filepath, len(content))
            return {"text": f"文件已保存：{filename}", "files": [filepath]}
        except Exception as e:
            logger.error("保存文件失败: %s", e)
            return {"text": f"保存失败: {e}", "files": []}


class WritePdfFileTool(BaseTool):
    """将文本保存为 PDF 文件"""

    def __init__(self):
        super().__init__(
            name="write_pdf_file",
            display_name="写PDF文件",
            description="将文本内容保存为 PDF 文件。可用于保存正式文档、报告等。",
            parameters={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "文件内容（纯文本，每行一个段落）",
                    },
                    "title": {
                        "type": "string",
                        "description": "文档标题（可选）",
                    },
                    "filename": {
                        "type": "string",
                        "description": "文件名，如'报告.pdf'，默认自动生成",
                    },
                },
                "required": ["content"],
            },
            final=True,
        )

    def execute(self, args: dict) -> dict:
        if not _HAS_FPDF:
            return {"text": "PDF 生成失败：未安装 fpdf2 库（pip install fpdf2）", "files": []}

        content = args.get("content", "").strip()
        if not content:
            return {"text": "内容为空", "files": []}

        title = args.get("title", "").strip()
        filename = args.get("filename", "").strip()
        if not filename:
            filename = f"output_{os.urandom(4).hex()}.pdf"
        if not filename.endswith(".pdf"):
            filename += ".pdf"

        try:
            filepath = _safe_path(filename)
            pdf = FPDF()
            pdf.add_page()
            if title:
                pdf.set_font("helvetica", "B", 16)
                pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(5)
            pdf.set_font("helvetica", "", 12)
            for line in content.split("\n"):
                line = line.strip()
                if line:
                    try:
                        pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
                    except Exception:
                        safe = line.encode("utf-8", errors="ignore").decode("utf-8")
                        pdf.cell(0, 8, safe, new_x="LMARGIN", new_y="NEXT")
                else:
                    pdf.ln(4)
            pdf.output(filepath)
            logger.info("PDF 文件已保存: %s (%d 字)", filepath, len(content))
            return {"text": f"PDF 已保存：{filename}", "files": [filepath]}
        except Exception as e:
            logger.error("生成 PDF 失败: %s", e)
            return {"text": f"生成 PDF 失败: {e}", "files": []}


class ReadTextFileTool(BaseTool):
    """从 temp 目录读取文件内容"""

    def __init__(self):
        super().__init__(
            name="read_text_file",
            display_name="读文本文件",
            description="读取 TEMP_DIR 内的文本文件内容。可用于读取之前保存的报告、笔记等。注意：只能读取 TEMP_DIR 目录下的文件。",
            parameters={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "文件名，如'成绩单.txt'",
                    },
                },
                "required": ["filename"],
            },
            silent=True,
        )

    def execute(self, args: dict) -> dict:
        filename = args.get("filename", "").strip()
        if not filename:
            return {"text": "请提供文件名", "files": []}

        try:
            filepath = _safe_path(filename)
            if not os.path.exists(filepath):
                return {"text": f"文件不存在：{filename}", "files": []}
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            return {"text": content, "files": []}
        except Exception as e:
            logger.error("读取文件失败: %s", e)
            return {"text": f"读取失败: {e}", "files": []}


class ReadPdfFileTool(BaseTool):
    """从 temp 目录读取 PDF 文件内容"""

    def __init__(self):
        super().__init__(
            name="read_pdf_file",
            display_name="读PDF文件",
            description="读取 TEMP_DIR 内的 PDF 文件内容（提取文字）。注意：只能读取 TEMP_DIR 目录下的文件。",
            parameters={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "文件名，如'报告.pdf'",
                    },
                },
                "required": ["filename"],
            },
            silent=True,
        )

    def execute(self, args: dict) -> dict:
        if not _HAS_PDF_READ:
            return {"text": "PDF 读取失败：未安装 PDF 库（pip install pypdf）", "files": []}

        filename = args.get("filename", "").strip()
        if not filename:
            return {"text": "请提供文件名", "files": []}

        try:
            filepath = _safe_path(filename)
            if not os.path.exists(filepath):
                return {"text": f"文件不存在：{filename}", "files": []}

            reader = _READER.PdfReader(filepath)
            pages = []
            for i, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text.strip():
                    pages.append(f"--- 第 {i} 页 ---\n{text.strip()}")
            content = "\n\n".join(pages) if pages else "（PDF 无文字内容）"
            logger.info("PDF 读取完成: %s (%d 页)", filepath, len(reader.pages))
            return {"text": content, "files": []}
        except Exception as e:
            logger.error("读取 PDF 失败: %s", e)
            return {"text": f"读取 PDF 失败: {e}", "files": []}


registry.register(WriteTextFileTool())
registry.register(WritePdfFileTool())
registry.register(ReadTextFileTool())
registry.register(ReadPdfFileTool())
