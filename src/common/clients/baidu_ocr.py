"""百度 OCR API 客户端 — 手写文字识别"""
import os
import base64
import urllib.parse
import logging
import requests

logger = logging.getLogger(__name__)


class BaiduOCR:
    """百度 OCR（手写体识别）"""

    def __init__(self):
        self._bearer_token = os.getenv("BAIDU_OCR_API_KEY", "")
        if not self._bearer_token:
            logger.warning("BAIDU_OCR_API_KEY 未设置")

    def recognize_handwriting(self, image_path: str, **kwargs) -> dict:
        """识别手写文字，返回 {"success": bool, "results": [...], "error": str}"""
        if not self._bearer_token:
            return {"success": False, "error": "BAIDU_OCR_API_KEY 未配置"}
        try:
            with open(image_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode("utf8")

            payload = '&'.join([
                f'image={urllib.parse.quote_plus(image_base64)}',
                'detect_direction=false',
                'probability=false',
                'detect_alteration=false',
            ])
            resp = requests.post(
                "https://aip.baidubce.com/rest/2.0/ocr/v1/handwriting",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Bearer {self._bearer_token}",
                },
                data=payload.encode("utf-8"),
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                if 'words_result' in data:
                    results = [{'text': item.get('words', ''), 'confidence': 1.0, 'text_region': []}
                               for item in data['words_result']]
                    return {"success": True, "results": results, "raw_result": data}
                return {"success": False, "error": data.get('error_msg', '未知错误'), "raw_result": data}
            return {"success": False, "error": f"HTTP {resp.status_code}", "raw_result": resp.text}
        except Exception as e:
            logger.error("OCR 识别失败: %s", e)
            return {"success": False, "error": str(e)}
