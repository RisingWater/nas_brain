"""OCR 文字识别工具 — 调用 PaddleOCR 共享库"""
import os
import logging
from . import BaseTool, registry
from src.common.lib.paddle_ocr import PaddleOCR

logger = logging.getLogger("brain_services.tools.ocr")


class OcrTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="ocr_image",
            display_name="OCR 文字识别",
            description="识别图片中的文字，返回识别结果。支持截图、拍照、扫描件等。",
            parameters={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "图片文件路径（绝对路径），如 /tmp/screenshot.png",
                    },
                },
                "required": ["image_path"],
            },
        )

    def execute(self, args: dict) -> dict:
        image_path = args.get("image_path", "")
        if not image_path:
            return {"text": "请提供图片路径"}
        if not os.path.exists(image_path):
            return {"text": f"文件不存在: {image_path}"}

        try:
            ocr = PaddleOCR()
            result = ocr.recognize(image_path)
            if result["success"]:
                text = result["text"]
                if not text:
                    return {"text": "未识别到文字"}
                return {"text": f"OCR 识别结果：\n{text}"}
            return {"text": f"OCR 识别失败: {result['error']}"}
        except Exception as e:
            logger.error("OCR 识别失败: %s", e)
            return {"text": f"OCR 识别失败: {e}"}


registry.register(OcrTool())
