"""文件格式转换工具 — 图片/文档转 PDF"""
import subprocess
import os
import logging
import img2pdf
from pathlib import Path

logger = logging.getLogger(__name__)


class FileConverter:
    """文件转换器（图片→PDF，文档→PDF）"""

    def convert_image_to_pdf(self, input_file: str, output_dir: str) -> str:
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"输入图片不存在: {input_file}")
        if output_dir is None:
            output_dir = os.path.dirname(input_file)
        input_name = Path(input_file).stem
        output_file = os.path.join(output_dir, f"{input_name}.pdf")
        try:
            with open(input_file, "rb") as image_file:
                with open(output_file, "wb") as pdf_file:
                    pdf_file.write(img2pdf.convert(image_file))
            logger.info("图片转换成功: %s → %s", input_name, output_file)
            return output_file
        except Exception as e:
            logger.error("图片转换失败: %s", e)
            raise

    def convert_document_to_pdf(self, input_file: str, output_dir: str = None) -> str:
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"输入文件不存在: {input_file}")
        if output_dir is None:
            output_dir = os.path.dirname(input_file)
        os.makedirs(output_dir, exist_ok=True)
        input_name = Path(input_file).stem
        output_file = os.path.join(output_dir, f"{input_name}.pdf")
        try:
            cmd = [
                'libreoffice', '--headless', '--convert-to', 'pdf:writer_pdf_Export',
                '--outdir', output_dir, input_file
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                logger.info("转换成功: %s → %s", input_file, output_file)
                return output_file
            raise Exception(f"文档转换失败: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise Exception("文档转换超时")
        except Exception as e:
            logger.error("转换异常: %s", e)
            raise

    def rasterize_pdf(self, input_file: str, output_dir: str = None, dpi: int = 200) -> str:
        """把 PDF 栅格化为图片 PDF（每页渲染为位图再重组）

        用途：规避部分打印机内置 PDF 解释器不支持内嵌 CJK 字体、
        直接打印文字版 PDF 出乱码的问题。栅格化后打印机只处理位图。
        """
        try:
            import pymupdf
        except ImportError:
            raise Exception("PDF 栅格化失败：未安装 pymupdf 库（pip install pymupdf）")
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"输入文件不存在: {input_file}")
        if output_dir is None:
            output_dir = os.path.dirname(input_file)
        stem = Path(input_file).stem
        output_file = os.path.join(output_dir, f"{stem}_raster.pdf")
        try:
            zoom = dpi / 72
            mat = pymupdf.Matrix(zoom, zoom)
            doc = pymupdf.open(input_file)
            pages = [page.get_pixmap(matrix=mat).tobytes("png") for page in doc]
            page_count = len(pages)
            doc.close()
            with open(output_file, "wb") as f:
                f.write(img2pdf.convert(pages))
            logger.info("PDF 栅格化成功: %s → %s (%d 页, %d DPI)",
                        input_file, output_file, page_count, dpi)
            return output_file
        except Exception as e:
            logger.error("PDF 栅格化失败: %s", e)
            raise

    def flatten_pdf_fonts(self, input_file: str, output_dir: str = None) -> str:
        """用 Ghostscript 把 PDF 内的所有文字转为矢量轮廓（-dNoOutputFonts）

        转换后 PDF 不再包含任何字体，打印机内置解释器无需渲染字体，
        规避内嵌 CJK 字体乱码问题；同时保留矢量属性，打印速度与文字版一致。
        """
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"输入文件不存在: {input_file}")
        if output_dir is None:
            output_dir = os.path.dirname(input_file)
        stem = Path(input_file).stem
        output_file = os.path.join(output_dir, f"{stem}_flat.pdf")
        try:
            cmd = [
                "gs", "-o", output_file, "-sDEVICE=pdfwrite",
                "-dNoOutputFonts", "-dNOPAUSE", "-dBATCH", "-dQUIET",
                input_file,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                raise Exception(f"gs 退出码 {result.returncode}: {result.stderr[:300]}")
            if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
                raise Exception("gs 未产生有效输出")
            logger.info("PDF 字体轮廓化成功: %s → %s", input_file, output_file)
            return output_file
        except FileNotFoundError:
            raise Exception("gs 命令不存在（未安装 ghostscript）")
        except subprocess.TimeoutExpired:
            raise Exception("gs 字体轮廓化超时")
        except Exception as e:
            logger.error("PDF 字体轮廓化失败: %s", e)
            raise
