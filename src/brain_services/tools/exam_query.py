"""考试成绩查询工具 — list_exams + get_exam_scores"""
import logging
from src.common.clients.zhixue import ZhixueAPI
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.exam_query")


class ListExamsTool(BaseTool):
    """列出最近考试"""

    def __init__(self):
        super().__init__(
            name="list_exams",
            display_name="列出考试",
            description="列出乔宝（王煜乔）最近的考试列表。调用此工具获取考试ID后，再用 get_exam_scores 查询具体分数。必须先调此工具。",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        )

    def execute(self, args: dict) -> dict:
        try:
            zhixue = ZhixueAPI()
            exams = zhixue.get_exam_list()
            if not exams:
                return {"text": "未查询到考试记录", "files": []}
            lines = ["最近考试："]
            for e in exams:
                lines.append(f"  {e['examName']}（ID: {e['examId']}）")
            return {"text": "\n".join(lines), "files": []}
        except Exception as e:
            logger.error("获取考试列表失败: %s", e, exc_info=True)
            return {"text": f"获取失败: {e}", "files": []}


class GetExamScoresTool(BaseTool):
    """获取指定考试的成绩"""

    def __init__(self):
        super().__init__(
            name="get_exam_scores",
            display_name="查询成绩",
            description="查询指定考试的各科成绩。可同时传入多个考试ID。考试ID需先通过 list_exams 获取。",
            parameters={
                "type": "object",
                "properties": {
                    "exam_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "考试ID列表，如 ['examId1', 'examId2']",
                    },
                },
                "required": ["exam_ids"],
            },
        )

    def execute(self, args: dict) -> dict:
        exam_ids = args.get("exam_ids", [])
        if not exam_ids:
            return {"text": "请提供考试ID（exam_ids）", "files": []}
        if isinstance(exam_ids, str):
            exam_ids = [exam_ids]

        try:
            zhixue = ZhixueAPI()
            results = []
            for eid in exam_ids:
                reports = zhixue.get_exam_report(eid)
                if not reports:
                    results.append(f"考试 {eid}：未找到成绩")
                    continue

                total = 0
                lines = [reports[0].get("paperName", "考试成绩")]
                for r in reports:
                    total += r.get("userScore", 0)
                    lines.append(
                        f"  {r['subjectName']}: {r['userScore']}/{r['standardScore']}"
                    )
                lines.append(f"  总分：{total}")
                results.append("\n".join(lines))

            return {"text": "\n\n".join(results), "files": []}
        except Exception as e:
            logger.error("获取考试成绩失败: %s", e, exc_info=True)
            return {"text": f"查询失败: {e}", "files": []}


registry.register(ListExamsTool())
registry.register(GetExamScoresTool())
