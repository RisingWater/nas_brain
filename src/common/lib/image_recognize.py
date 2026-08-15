"""图片识别客户端 — 调用图片识别 LLM（OpenCode Go MiMo-V2.5 等）

OpenAI 兼容的 chat/completions 端点，把图片压缩后以 base64 data URI 传给
多模态模型识别内容。

配置（.env）：
    IMAGE_RECOGNIZE_API_URL=OpenAI 兼容端点
    IMAGE_RECOGNIZE_API_KEY=API Key
    IMAGE_RECOGNIZE_MODEL_NAME=模型名（如 mimo-v2.5）

可选：传入 OCR 结果时，提示词会补充"此图片经过 OCR，识别出的文字是 xxx"，
帮助模型结合 OCR 文字与图像内容回答。
"""
import base64
import io
import logging
import os

import requests
from PIL import Image

logger = logging.getLogger(__name__)

_IMAGE_URL = os.getenv("IMAGE_RECOGNIZE_API_URL", "").strip()
_IMAGE_API_KEY = os.getenv("IMAGE_RECOGNIZE_API_KEY", "").strip()
_IMAGE_MODEL = os.getenv("IMAGE_RECOGNIZE_MODEL_NAME", "").strip()

MAX_LONG_EDGE = 1024  # 压缩后长边像素（宽高比不变）


class ImageRecognizer:
    """图片识别 LLM 客户端"""

    def __init__(self, url: str = "", api_key: str = "", model: str = ""):
        self._url = url or _IMAGE_URL
        self._api_key = api_key or _IMAGE_API_KEY
        self._model = model or _IMAGE_MODEL

    def recognize(self, image_path: str, ocr_text: str = "", prompt: str = "") -> dict:
        """识别图片内容，返回 {"success": bool, "text": str, "error": str}

        Args:
            image_path: 图片文件路径
            ocr_text: 该图片经过 OCR 识别出的文字（可选，有则拼进提示词）
            prompt: 自定义识别指令（默认识别当前图片内容）
        """
        if not self._api_key or not self._model:
            return {"success": False, "text": "", "error": "未配置 IMAGE_RECOGNIZE_API_KEY / IMAGE_RECOGNIZE_MODEL_NAME"}
        if not os.path.exists(image_path):
            return {"success": False, "text": "", "error": f"文件不存在: {image_path}"}
        try:
            data_uri = self._image_to_data_uri(image_path)
            user_prompt = self._build_prompt(prompt, ocr_text)
            payload = {
                "model": self._model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {"type": "image_url", "image_url": {"url": data_uri}},
                        ],
                    }
                ],
                "max_tokens": 2000,
                "temperature": 0.3,
            }
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
            resp = requests.post(self._url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return {"success": True, "text": content or "", "error": ""}
        except Exception as e:
            logger.error("图片识别失败: %s", e)
            return {"success": False, "text": "", "error": str(e)}

    def _build_prompt(self, prompt: str, ocr_text: str) -> str:
        """组装提示词：默认识别图片内容；有 OCR 结果时补充说明"""
        if prompt:
            user_prompt = prompt
        else:
            user_prompt = "请识别这张图片的内容，并尽可能详细地用中文描述图片中看到的一切。"
        if ocr_text and ocr_text.strip():
            user_prompt += f"\n此图片经过 OCR，识别出来的文字是：{ocr_text.strip()}"
        return user_prompt

    @staticmethod
    def _image_to_data_uri(path: str) -> str:
        """压缩图片（长边缩到 MAX_LONG_EDGE，宽高比不变；小图不放大），
        统一转 RGB + JPEG 压缩后 base64 编码"""
        img = Image.open(path)
        img.load()
        width, height = img.size
        long_edge = max(width, height)
        if long_edge > MAX_LONG_EDGE:
            scale = MAX_LONG_EDGE / long_edge
            new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
            img = img.resize(new_size, Image.LANCZOS)
            logger.info("图片压缩: %dx%d -> %dx%d", width, height, new_size[0], new_size[1])
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        data = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{data}"


# 全局默认实例
_default_recognizer = None


def get_image_recognizer() -> ImageRecognizer:
    global _default_recognizer
    if _default_recognizer is None:
        _default_recognizer = ImageRecognizer()
    return _default_recognizer


def image_recognize(image_path: str, ocr_text: str = "", prompt: str = "") -> str:
    """便捷函数：直接返回识别文本（失败返回空字符串）"""
    result = get_image_recognizer().recognize(image_path, ocr_text, prompt)
    return result["text"] if result["success"] else ""
