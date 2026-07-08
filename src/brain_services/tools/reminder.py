"""定时提醒工具 — 文件存储，添加/列出/删除"""
import json
import os
import logging
from datetime import datetime
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.reminder")

_REMINDER_FILE = os.getenv("REMINDER_FILE", "data/reminders.json")


def _load() -> list:
    if not os.path.exists(_REMINDER_FILE):
        return []
    with open(_REMINDER_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save(reminders: list):
    os.makedirs(os.path.dirname(_REMINDER_FILE) or ".", exist_ok=True)
    with open(_REMINDER_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)


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
            reminders = _load()
            new_id = max((r["id"] for r in reminders), default=0) + 1
            reminders.append({
                "id": new_id,
                "content": args["content"],
                "rtype": args["rtype"],
                "datetime": args["datetime"],
                "created_at": datetime.now().isoformat(),
                "done": False,
            })
            _save(reminders)
            return f"提醒已设置：{args['content']}"
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
            reminders = [r for r in _load() if not r.get("done")]
            if not reminders:
                return "没有待执行的提醒"
            lines = []
            type_cn = {"once": "一次性", "daily": "每天", "monthly": "每月"}
            for r in reminders:
                lines.append(f"#{r['id']} [{type_cn.get(r['rtype'], r['rtype'])}] "
                             f"{r['datetime']} — {r['content']}")
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
            reminders = _load()
            reminders = [r for r in reminders if r["id"] != args["reminder_id"]]
            _save(reminders)
            return "提醒已经删除"
        except Exception as e:
            return f"删除失败：{e}"


registry.register(AddReminderTool())
registry.register(ListRemindersTool())
registry.register(DeleteReminderTool())
