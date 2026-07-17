"""exam_detector — 考试成绩检测插件（移植自 wechat_bot/detector/exam_loop.py）"""
import logging
from .base import BaseDetector, DetectorContext, registry
from src.common.clients.kv_store import kv_store

logger = logging.getLogger("schedule_services.detector.exam")

router_data = [
    {"chatname": "学霸乔宝专项配套办公室"},
]


class ExamDetector(BaseDetector):
    """智学网考试成绩检测

    轮询智学网 API，发现新成绩 → 微信通知 + 汇总
    """

    name = "exam"
    interval = 300  # 5 分钟

    def __init__(self):
        super().__init__()
        self._zhixue = None

    def _get_zhixue(self):
        if self._zhixue is None:
            from src.common.clients.zhixue import ZhixueAPI
            self._zhixue = ZhixueAPI()
        return self._zhixue

    def process_loop(self, ctx: DetectorContext):
        try:
            zhixue = self._get_zhixue()
            exam_list = zhixue.get_exam_list()[-5:]

            for exam in exam_list:
                exam_id = exam.get("examId")
                exam_name = exam.get("examName")
                logger.info("正在获取考试: %s", exam_name)

                report_data = zhixue.get_exam_report(exam_id)
                has_new = False

                for report in report_data:
                    paper_id = report.get("paperId")
                    config_key = f"EXAM_NOTIFIED_{paper_id}"

                    if kv_store.exists(config_key):
                        continue

                    has_new = True
                    logger.info("发现新成绩: %s", report.get("paperName"))

                    for route in router_data:
                        chatname = route.get("chatname")
                        if chatname:
                            msg = f"🎉🎉🎉 乔宝 {report.get('paperName')} 成绩出来啦，分数{report.get('userScore')}"
                            ctx.send_wechat(chatname, msg)

                    kv_store.set(config_key, "1", namespace="exam")

                if has_new:
                    for route in router_data:
                        chatname = route.get("chatname")
                        if chatname:
                            total_score = 0
                            lines = [f"{exam_name}"]
                            for report in report_data:
                                total_score += report.get("userScore", 0)
                                lines.append(f"{report.get('subjectName')}: {report.get('userScore')}")
                            lines.append(f"目前总分：{total_score}")
                            ctx.send_wechat(chatname, "\n".join(lines))

        except Exception as e:
            logger.error("考试成绩检测异常: %s", e, exc_info=True)


registry.register(ExamDetector())
