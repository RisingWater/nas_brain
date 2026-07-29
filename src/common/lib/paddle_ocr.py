"""PaddleOCR 客户端 — 调用 PaddleOCR Simple Server"""
import logging
import os
import requests

logger = logging.getLogger(__name__)

_OCR_URL = os.getenv("OCR_SERVER_URL", "http://localhost:3000/recognize")
_OCR_TOKEN = os.getenv("OCR_SERVER_TOKEN", "")


class PaddleOCR:
    """PaddleOCR 文字识别客户端"""

    def __init__(self, url: str = "", token: str = ""):
        self._url = url or _OCR_URL
        self._token = token or _OCR_TOKEN

    def recognize(self, image_path: str) -> dict:
        """识别图片文字，返回 {"success": bool, "text": str, "items": list, "error": str}"""
        if not os.path.exists(image_path):
            return {"success": False, "text": "", "items": [], "error": f"文件不存在: {image_path}"}
        try:
            with open(image_path, "rb") as f:
                headers = {}
                if self._token:
                    headers["Authorization"] = f"Bearer {self._token}"
                resp = requests.post(self._url, files={"img": f}, headers=headers, timeout=30)
            logger.info("PaddleOCR raw: %s %s", resp.status_code, resp.text[:500])
            resp.raise_for_status()
            data = resp.json()
            # PaddleOCR Simple Server 返回: {"text": "...", "lines": [[{"text":"...","confidence":...}]]}
            if "text" in data and data["text"]:
                return {"success": True, "text": data["text"], "items": data.get("lines", []), "error": ""}
            # 兼容其他格式
            items = data.get("data", data.get("result", []))
            if not items:
                return {"success": True, "text": "", "items": [], "error": ""}
            texts = []
            for item in items:
                if isinstance(item, dict):
                    texts.append(item.get("text", str(item)))
                elif isinstance(item, str):
                    texts.append(item)
                else:
                    texts.append(str(item))
            return {"success": True, "text": "\n".join(texts), "items": items, "error": ""}
        except Exception as e:
            logger.error("PaddleOCR 识别失败: %s", e)
            return {"success": False, "text": "", "items": [], "error": str(e)}


# 全局默认实例
_default_ocr = None


def get_ocr() -> PaddleOCR:
    global _default_ocr
    if _default_ocr is None:
        _default_ocr = PaddleOCR()
    return _default_ocr


def ocr_recognize(image_path: str) -> str:
    """便捷函数：直接返回识别文本"""
    result = get_ocr().recognize(image_path)
    return result["text"]
