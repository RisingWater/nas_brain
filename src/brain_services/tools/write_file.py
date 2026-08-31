"""文件读写工具 — 在 TEMP_DIR 内读写文件，支持 txt/pdf"""
import glob
import os
import sys
import logging
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.write_file")

_TEMP_DIR = os.path.normpath(os.getenv("TEMP_DIR", "data"))

# CJK 字体文件名匹配模式（用于扫描系统字体目录）
_CJK_FONT_PATTERNS = [
    "*NotoSansCJK*", "*NotoSansSC*", "*SourceHanSans*",
    "wqy*", "WenQuanYi*", "*DroidSansFallback*",
    "*simhei*", "*msyh*", "*ukai*", "*uming*",
]

# 解析缓存：None=未扫描，""=扫描过但无可加载字体，其他=可用字体路径
_CJK_FONT_RESOLVED: str | None = None


def _linux_cjk_fonts() -> list[str]:
    """扫描 Linux 常见字体目录，返回 CJK 字体路径（ttf/otf 优先于 ttc）"""
    hits: list[str] = []
    for root in ("/usr/share/fonts", "/usr/local/share/fonts",
                 os.path.expanduser("~/.fonts")):
        if not os.path.isdir(root):
            continue
        for ext in ("ttf", "otf", "ttc"):
            for pat in _CJK_FONT_PATTERNS:
                hits.extend(glob.glob(
                    os.path.join(root, "**", f"{pat}.{ext}"), recursive=True))
    # 去重保序
    seen: set[str] = set()
    return [p for p in hits if not (p in seen or seen.add(p))]


def _cjk_font_candidates() -> list[str]:
    """按优先级组装 CJK 字体候选路径"""
    cands = [
        os.getenv("PDF_FONT_PATH", ""),
        os.path.join(_TEMP_DIR, "NotoSansSC-Regular.otf"),
        os.path.join(_TEMP_DIR, "fonts", "NotoSansSC-Regular.otf"),
    ]
    if sys.platform.startswith("linux"):
        cands += _linux_cjk_fonts()
        cands.append("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf")
    else:
        cands += [r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc"]
    return [c for c in cands if c]

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


def _cjk_font_path() -> str:
    """解析并缓存第一个可加载的 CJK 字体路径（每次进程只扫描一次）"""
    global _CJK_FONT_RESOLVED
    if _CJK_FONT_RESOLVED is not None:
        return _CJK_FONT_RESOLVED
    if not _HAS_FPDF:
        _CJK_FONT_RESOLVED = ""
        return ""
    for path in _cjk_font_candidates():
        try:
            # 用一次性 FPDF 实际验证字体可加载（排除损坏/不兼容文件）
            pdf = FPDF()
            pdf.add_font("cjk", "", path)
            _CJK_FONT_RESOLVED = path
            logger.info("PDF 中文字体: %s", path)
            break
        except Exception as e:
            logger.debug("字体不可加载 %s: %s", path, e)
    else:
        _CJK_FONT_RESOLVED = ""
        logger.warning("未找到可用的 CJK 字体，write_pdf_file 不支持中文")
    return _CJK_FONT_RESOLVED


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

        # 字体选择：优先 CJK 字体（支持中文）；无中文且纯 ASCII 可用内置 helvetica
        font_path = _cjk_font_path()
        if not font_path and not content.isascii():
            return {"text": "生成 PDF 失败：未找到中文字体（可配置 PDF_FONT_PATH 环境变量，"
                            "或将 NotoSansSC-Regular.otf 放入临时文件目录）", "files": []}

        try:
            filepath = _safe_path(filename)
            pdf = FPDF()
            pdf.add_page()
            if font_path:
                pdf.add_font("cjk", "", font_path)
                pdf.add_font("cjk", "B", font_path)
                title_font = ("cjk", "B")
                body_font = ("cjk", "")
            else:
                title_font = ("helvetica", "B")
                body_font = ("helvetica", "")
            if title:
                pdf.set_font(*title_font, 16)
                pdf.multi_cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(5)
            pdf.set_font(*body_font, 12)
            for line in content.split("\n"):
                line = line.rstrip()
                if line:
                    # multi_cell 自动换行（长行/中文均安全）
                    pdf.multi_cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
                else:
                    pdf.ln(4)
            pdf.output(filepath)
            logger.info("PDF 文件已保存: %s (%d 字, 字体=%s)",
                        filepath, len(content), font_path or "helvetica")
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
