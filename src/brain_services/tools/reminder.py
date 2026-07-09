"""定时提醒工具 — 通过 schedule_services API 管理，替代原有 JSON 文件"""
import logging
import requests
from datetime import datetime
from src.common.utils import cfg
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.reminder")

_SCHEDULE_URL = cfg.get_service_url("schedule_services", "/api/schedules")


def _call(method: str, path: str = "", json_data: dict = None, params: dict = None) -> dict | None:
    """调用 schedule_services API"""
    url = f"{_SCHEDULE_URL}{path}"
    try:
        if method == "GET":
            resp = requests.get(url, params=params, timeout=10)
        elif method == "POST":
            resp = requests.post(url, json=json_data, timeout=10)
        elif method == "DELETE":
            resp = requests.delete(url, timeout=10)
        else:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("schedule_services 调用失败: %s", e)
        return None


class AddReminderTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="add_reminder",
            description="添加一个定时提醒。支持一次性、每天、每月。例如：'晚上9点提醒我吃药'、'明天下午3点开会'。",
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "提醒内容"},
                    "rtype": {"type": "string", "enum": ["once", "daily", "monthly"],
                              "description": "once=一次性, daily=每天, monthly=每月"},
                    "datetime": {"type": "string",
                                 "description": "时间：once用'2026-06-18 21:00'，daily用'21:00'，monthly用'15 21:00'"},
                },
                "required": ["content", "rtype", "datetime"],
            },
            final=True,
        )

    def execute(self, args: dict) -> str:
        try:
            data = {
                "user_id": "u_system",
                "content": args["content"],
                "rtype": args["rtype"],
                "rdatetime": args["datetime"],
                "strategy": "direct",
                "notify_type": "wechat",
            }
            result = _call("POST", "", json_data=data)
            if result and result.get("code") == 201:
                return f"提醒已设置：{args['content']}"
            return f"设置失败：{result}"
        except Exception as e:
            return f"添加提醒失败：{e}"


class ListRemindersTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="list_reminders",
            description="列出所有未完成的定时提醒。",
            parameters={"type": "object", "properties": {}, "required": []},
            silent=True,
        )

    def execute(self, args: dict) -> str:
        try:
            result = _call("GET", "", params={"done": "false"})
            if not result:
                return "查询失败"
            schedules = result.get("data", {}).get("schedules", [])
            if not schedules:
                return "没有待执行的提醒"
            lines = []
            type_cn = {"once": "一次性", "daily": "每天", "monthly": "每月"}
            for s in schedules:
                lines.append(f"#{s['id']} [{type_cn.get(s['rtype'], s['rtype'])}] "
                             f"{s['rdatetime'] or ''} — {s['content']}")
            return "\n".join(lines)
        except Exception as e:
            return f"查询失败：{e}"


class DeleteReminderTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="delete_reminder",
            description="删除一个定时提醒。",
            parameters={
                "type": "object",
                "properties": {"reminder_id": {"type": "integer", "description": "提醒编号（#id）"}},
                "required": ["reminder_id"],
            },
            silent=True, final=True,
        )

    def execute(self, args: dict) -> str:
        try:
            result = _call("DELETE", f"/{args['reminder_id']}")
            if result and result.get("code") == 200:
                return "提醒已删除"
            return f"删除失败：{result}"
        except Exception as e:
            return f"删除失败：{e}"


registry.register(AddReminderTool())
registry.register(ListRemindersTool())
registry.register(DeleteReminderTool())
