"""文件格式识别工具 — 通过二进制内容识别 PDF/DOC/DOCX/WPS"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FileRecognizer:
    """文件格式识别器"""

    def _read_header(self, file_path: str, n: int = 16) -> Optional[bytes]:
        try:
            with open(file_path, 'rb') as f:
                return f.read(n)
        except Exception as e:
            logger.error("读取文件头失败 %s: %s", file_path, e)
            return None

    def get_extension(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return '.unknown'
        if self._is_pdf(file_path):      return '.pdf'
        if self._is_docx(file_path):     return '.docx'
        if self._is_wps(file_path):      return '.wps'
        if self._is_doc(file_path):      return '.doc'
        return '.unknown'

    def _is_pdf(self, file_path: str) -> bool:
        header = self._read_header(file_path, 8)
        if not header:
            return False
        if header.startswith(b'%PDF-') or b'%PDF-' in header[:4]:
            return True
        return False

    def _is_doc(self, file_path: str) -> bool:
        header = self._read_header(file_path, 8)
        return bool(header and header.startswith(b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'))

    def _is_docx(self, file_path: str) -> bool:
        header = self._read_header(file_path, 4)
        if not header or not header.startswith(b'PK\x03\x04'):
            return False
        try:
            with open(file_path, 'rb') as f:
                data = f.read(2000)
            return b'word/' in data or b'[Content_Types].xml' in data
        except Exception:
            return False

    def _is_wps(self, file_path: str) -> bool:
        try:
            with open(file_path, 'rb') as f:
                header = f.read(32)
            if header.startswith(b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'):
                with open(file_path, 'rb') as f:
                    data = f.read(4096)
                for ident in [b'WPS Office', b'Kingsoft WPS', b'WPSWriter']:
                    if ident in data:
                        return True
                _, ext = os.path.splitext(file_path)
                if ext.lower() in ('.wps', '.et', '.dps'):
                    return True
            elif header.startswith(b'PK\x03\x04'):
                with open(file_path, 'rb') as f:
                    data = f.read(8192)
                if b'wps.xml' in data or b'WPSDocument' in data:
                    return True
            return False
        except Exception:
            return False
