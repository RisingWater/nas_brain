"""文档打印处理器 — 接收图片/文档文件，通过 CUPS 网络打印机输出（仅 Linux）

图片处理：用多模态 LLM（mimo 2.5）识别图片类型（截图/手拍照片）及二值化参数。
截图直接打印；手拍照片按 LLM 给出的参数二值化（有阴影先去阴影再二值化，无阴影直接二值化）。
LLM 识别/JSON 解析失败时报错不打印。

打印任务提交后启动后台线程监控 job 状态，完成/失败/超时均推送微信。
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import logging
from . import BaseProcessor, registry
from src.common.schemas.agent_request import AgentRequest, ContentType
from src.common.lib.file_converter import FileConverter
from src.common.lib.file_recognize import FileRecognizer
from src.common.lib.image_binarize import ImageBinarrize
from src.common.lib.image_recognize import get_image_recognizer
from src.common.lib.printer import Printer

logger = logging.getLogger(__name__)

SUPPORTED_EXT = {'.doc', '.docx', '.pdf', '.wps'}

# LLM 判定图片类型与二值化参数的提示词（要求只输出合法 JSON）
_CLASSIFY_PROMPT = (
    "请分析这张图片，判断它属于以下三种类型之一，并给出二值化建议。"
    "只输出一个合法的 JSON 对象，不要输出任何其他内容，格式如下：\n"
    '{"type": "screenshot" 或 "document" 或 "photo", "has_shadow": true/false, "threshold": 0-255, "invert": true/false}\n'
    "说明：\n"
    "- type: 电脑/手机屏幕截图填 screenshot；拍摄的纸质文档/作业/试卷（含纸张背景和文字内容）填 document；"
    "其他拍摄的照片（人、风景、实物等，无文字为主的纸质内容）填 photo\n"
    "- has_shadow: 图片是否存在阴影或光照不均（仅 document 需要判断，screenshot/photo 填 false）\n"
    "- threshold: 二值化灰度阈值，0-255，建议选能把文字/内容与背景干净分离的值（仅 document 填写，screenshot/photo 填 192）\n"
    "- invert: 背景浅文字深填 false；背景深文字浅（如白字黑底）填 true"
)

# CUPS 任务终态
_JOB_DONE = {"completed", "canceled", "aborted"}
_JOB_TIMEOUT_CHECKS = 100  # 最多检查 100 次（每 3 秒，约 5 分钟）
_JOB_CHECK_INTERVAL = 3  # 秒


class PrintProcessor(BaseProcessor):
    name = "print"
    description = "文档打印处理器（仅 Linux）"

    def priority(self) -> int:
        return 10

    def can_handle(self, req: AgentRequest) -> bool:
        # 图片和文件
        return req.content_type in (ContentType.IMAGE, ContentType.FILE)

    def handle(self, req: AgentRequest, ctx) -> dict | None:
        printer = Printer()
        if not printer.is_ready:
            ctx.reply("打印机未就绪（请检查 PRINTER_NAME 配置）")
            return {"reply": "打印机未就绪"}

        if not req.file_id:
            return None

        file_data = ctx.download_file(req.file_id)
        if not file_data:
            ctx.reply("下载文件失败")
            return {"reply": "下载文件失败"}

        who = (req.metadata or {}).get("wechat_name", "")

        tmpdir = tempfile.mkdtemp()
        try:
            # 猜测文件名和扩展名
            meta = req.metadata or {}
            file_name = meta.get("file_name", "print_file")
            file_path = os.path.join(tmpdir, file_name)
            with open(file_path, "wb") as f:
                f.write(file_data)

            converter = FileConverter()
            recognizer = FileRecognizer()
            ext = recognizer.get_extension(file_path)

            # 图片 → 分类 → 二值化/原样 → PDF → 打印
            if req.content_type == ContentType.IMAGE:
                params = self._classify_image(file_path)
                if params is None:
                    ctx.reply("无法识别图片类型（截图/文档/照片），已取消打印")
                    return {"reply": "无法识别图片类型（截图/文档/照片），已取消打印"}

                if params["type"] == "document":
                    # 手拍文档：有阴影先去阴影，再按 LLM 阈值二值化
                    logger.info("图片判定为手拍文档，二值化处理（去阴影=%s, 阈值=%s, 反色=%s）",
                                params["has_shadow"], params["threshold"], params["invert"])
                    binarized = os.path.join(tmpdir, "binarized_" + file_name)
                    binarizer = ImageBinarrize()
                    binarizer.process_image(
                        file_path, binarized,
                        threshold=params["threshold"],
                        remove_shadow=params["has_shadow"],
                        invert=params["invert"],
                    )
                    pdf_path = converter.convert_image_to_pdf(binarized, tmpdir)
                else:
                    # 截图 / 普通照片：直接打印
                    logger.info("图片判定为 %s，直接打印", params["type"])
                    pdf_path = converter.convert_image_to_pdf(file_path, tmpdir)
            elif ext in SUPPORTED_EXT and ext != ".pdf":
                pdf_path = converter.convert_document_to_pdf(file_path, tmpdir)
            elif ext == ".pdf":
                pdf_path = file_path
            else:
                ctx.reply(f"不支持的文件格式: {ext}")
                return {"reply": f"不支持的文件格式: {ext}"}

            success, job_id = printer.print_pdf(pdf_path)
            if success:
                ctx.reply(f"打印任务已创建: {job_id}")
                self._start_job_monitor(job_id, who, file_name, ctx)
                return {"reply": f"打印任务已创建: {job_id}"}
            ctx.reply(f"打印失败: {job_id}")
            return {"reply": f"打印失败: {job_id}"}

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @staticmethod
    def _parse_bool(value) -> bool:
        """解析布尔字段（兼容 bool / int / 字符串 true/false）"""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value).strip().lower() in ("true", "1", "yes", "on")

    def _classify_image(self, image_path: str) -> dict | None:
        """调用多模态 LLM 判定图片类型与二值化参数，返回解析后的 dict

        返回 {"type", "has_shadow", "threshold", "invert"}；
        识别失败 / JSON 非法 / 字段缺失 / 类型不合法时返回 None。
        """
        text = ""
        try:
            t0 = time.monotonic()
            result = get_image_recognizer().recognize(image_path, prompt=_CLASSIFY_PROMPT)
            logger.info("图片分类 LLM 调用完成，耗时 %.1fs", time.monotonic() - t0)
            if not result["success"]:
                logger.warning("图片分类识别失败: %s", result.get("error"))
                return None
            text = (result["text"] or "").strip()
            # 去掉可能的代码块围栏
            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)
            img_type = str(data.get("type", "")).strip().lower()
            if img_type not in ("screenshot", "document", "photo"):
                logger.warning("图片类型不合法: %r", img_type)
                return None
            params = {
                "type": img_type,
                "has_shadow": self._parse_bool(data.get("has_shadow", False)),
                "threshold": int(data.get("threshold", 192)),
                "invert": self._parse_bool(data.get("invert", False)),
            }
            logger.info("图片分类完成: type=%s, has_shadow=%s, threshold=%s, invert=%s",
                        params["type"], params["has_shadow"], params["threshold"], params["invert"])
            return params
        except Exception as e:
            logger.warning("图片分类 JSON 解析失败: %s (text=%r)", e, text)
            return None

    def _start_job_monitor(self, job_id: str, who: str, file_name: str, ctx):
        """启动打印任务状态监控线程（守护线程，完成后推送微信）"""
        def monitor():
            logger.info("开始监控打印任务 %s", job_id)
            for _ in range(_JOB_TIMEOUT_CHECKS):
                try:
                    status = Printer().get_job_status(job_id)
                    state = status.get("state_name", "unknown")
                    if state in _JOB_DONE:
                        if state == "completed":
                            ctx.send_wechat(who, f"✅ 打印任务{job_id}, {file_name} 已打印完成")
                            logger.info("打印任务 %s 完成", job_id)
                        else:
                            ctx.send_wechat(who, f"❌ 打印任务{job_id}, {file_name} 打印失败, 当前状态{state}")
                            logger.warning("打印任务 %s 结束: %s", job_id, state)
                        return
                    time.sleep(_JOB_CHECK_INTERVAL)
                except Exception as e:
                    logger.error("监控打印任务 %s 异常: %s", job_id, e)
                    time.sleep(_JOB_CHECK_INTERVAL)
            if who:
                ctx.send_wechat(who, "打印任务监控超时，请手动检查打印机状态")
            logger.warning("打印任务 %s 监控超时", job_id)

        threading.Thread(
            target=monitor,
            daemon=True,
            name=f"PrintMonitor-{job_id}",
        ).start()
        logger.info("已启动打印任务 %s 监控线程", job_id)


# 仅 Linux 注册（Windows 下无 CUPS 驱动）
if sys.platform != "win32":
    registry.register(PrintProcessor())
else:
    logger.info("Windows 平台，跳过注册 print processor")


if __name__ == "__main__":
    # 本地测试入口（Windows 可跑）：仅测 mimo 图片分类，不打印
    # 用法: python -m src.brain_services.processors.print <图片路径> [更多图片路径...]
    import importlib
    import logging

    # image_recognize 的配置在模块导入时读取，这里加载 .env 后重载使其生效
    from dotenv import load_dotenv
    load_dotenv(override=True)
    import src.common.lib.image_recognize as _ir
    importlib.reload(_ir)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if len(sys.argv) < 2:
        print("用法: python -m src.brain_services.processors.print <图片路径> [更多图片路径...]")
        sys.exit(1)

    _DECISION = {
        "screenshot": "截图 → 直接打印",
        "photo": "普通照片 → 直接打印",
        "document": "手拍文档 → 二值化后打印",
    }

    _proc = PrintProcessor()
    for _path in sys.argv[1:]:
        print(f"\n=== 分类: {_path} ===")
        _t0 = time.monotonic()
        _params = _proc._classify_image(_path)
        _dt = time.monotonic() - _t0
        if _params is None:
            print(f"✗ 分类失败（原因见上方日志），耗时 {_dt:.1f}s")
        else:
            print(json.dumps(_params, ensure_ascii=False, indent=2))
            print(f"→ {_DECISION[_params['type']]}")
            print(f"✓ 耗时 {_dt:.1f}s")