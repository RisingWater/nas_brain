"""作业 OCR 处理器 — 识别作业图片内容，用 DeepSeek 整理"""
import os
import shutil
import tempfile
import logging
from . import BaseProcessor, registry
from src.common.schemas.agent_request import AgentRequest, ContentType
from src.common.clients.baidu_ocr import BaiduOCR
from src.common.clients.deepseek import DeepSeekAPI

logger = logging.getLogger(__name__)


class HomeworkProcessor(BaseProcessor):
    name = "homework"
    description = "作业 OCR 处理器"

    def priority(self) -> int:
        return 10

    def can_handle(self, req: AgentRequest) -> bool:
        return req.content_type == ContentType.IMAGE

    def handle(self, req: AgentRequest, ctx) -> dict | None:
        if not req.file_id:
            ctx.reply("没有找到图片")
            return {"reply": "没有找到图片"}

        file_data = ctx.download_file(req.file_id)
        if not file_data:
            ctx.reply("下载图片失败")
            return {"reply": "下载图片失败"}

        tmpdir = tempfile.mkdtemp()
        try:
            # 保存图片
            ext = ".jpg"
            img_path = os.path.join(tmpdir, f"homework{ext}")
            with open(img_path, "wb") as f:
                f.write(file_data)

            # OCR
            ocr = BaiduOCR()
            ocr_result = ocr.recognize_handwriting(img_path)
            if not ocr_result.get("success"):
                ctx.reply(f"图片识别失败: {ocr_result.get('error')}")
                return {"reply": f"图片识别失败: {ocr_result.get('error')}"}

            # 用 DeepSeek 整理
            texts = [item['text'] for item in ocr_result['results']]
            ocr_content = "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts))
            prompt = f"""请分析并整理以下从作业图片中识别出的文字内容，这些内容可能有分栏布局。

OCR识别结果：
{ocr_content}

请按照以下要求处理：
1. 分析文字之间的空间关系和布局结构
2. 将内容按逻辑整理
3. 如果检测到多个班级或部分，请明确分开
4. 不要使用Markdown格式

示例格式：
十月十日
语文:
1.阳光课堂练习P43-46.
2.准备小测
数学:
1.卷子一张:P67-P68.

请只输出整理后的文本内容，不要添加额外的解释说明。如果识别结果与作业无关请直接输出"这不是作业"。"""

            deepseek = DeepSeekAPI()
            organized = deepseek.ask_single_question(prompt)
            reply = organized or "（OCR 识别完成，但整理失败）"
            ctx.reply(reply)
            return {"reply": reply}

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


registry.register(HomeworkProcessor())
