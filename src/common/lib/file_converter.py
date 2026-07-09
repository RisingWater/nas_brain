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
