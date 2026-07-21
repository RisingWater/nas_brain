"""定时提醒工具 — 通过 schedule_services API 管理，替代原有 JSON 文件"""
import logging
import requests
from datetime import datetime
from src.common.utils import cfg
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.reminder")

_SCHEDULE_URL = cfg.get_service_url("schedule_services", "/api/schedules")

_TYPE_CN = {"once": "一次性", "daily": "每天", "monthly": "每月"}


def _call(method: str, path: str = "", json_data: dict = None, params: dict = None) -> dict | None:
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
            display_name="添加提醒",
            description=(
                "添加一个定时提醒。支持一次性、每天、每月。"
                "时间格式：一次性='2026-07-09 21:00'，每天='21:00'，每月='15 21:00'（15号21点）。"
                "不指定接收人则默认发给设置者自己，也可指定微信名或群名。"
                "例如：用户说'每天晚上9点提醒我吃药'→content=吃药,rtype=daily,datetime=21:00。"
                "用户说'明天下午3点在群里提醒大家开会'→content=明天下午3点开会,rtype=once,datetime=具体时间。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "提醒内容，如'吃药'、'开会'"},
                    "rtype": {"type": "string", "enum": ["once", "daily", "monthly"],
                              "description": "once=一次性, daily=每天, monthly=每月"},
                    "datetime": {"type": "string",
                                 "description": "时间：once用'2026-07-09 21:00'，daily用'21:00'，monthly用'15 21:00'"},
                    "notify_target": {
                        "type": "string",
                        "description": "接收人微信名或群名（可选，不填默认发给设置者自己）",
                    },
                },
                "required": ["content", "rtype", "datetime"],
            },
            final=True,
        )

    def execute(self, args: dict) -> dict:
        try:
            data = {
                "creator_id": "u_system",
                "content": args["content"],
                "rtype": args["rtype"],
                "rdatetime": args["datetime"],
                "strategy": "direct",
                "notify_type": "wechat",
            }
            if args.get("notify_target"):
                data["notify_target"] = args["notify_target"]

            result = _call("POST", "", json_data=data)
            if result and result.get("code") == 201:
                msg = f"提醒已设置：{args['content']}"
                if args.get("notify_target"):
                    msg += f"（通知：{args['notify_target']}）"
                return {"text": msg}
            return {"text": f"设置失败：{result}"}
        except Exception as e:
            return {"text": f"添加提醒失败：{e}"}


class ListRemindersTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="list_reminders",
            display_name="列出提醒",
            description="列出所有未完成的定时提醒。",
            parameters={"type": "object", "properties": {}, "required": []},
            silent=True,
        )

    def execute(self, args: dict) -> dict:
        try:
            result = _call("GET", "", params={"done": "false"})
            if not result:
                return {"text": "查询失败"}
            schedules = result.get("data", {}).get("schedules", [])
            if not schedules:
                return {"text": "没有待执行的提醒"}
            lines = []
            for s in schedules:
                target = s.get("notify_target") or "自己"
                lines.append(f"#{s['id']} [{_TYPE_CN.get(s['rtype'], s['rtype'])}] "
                             f"{s['rdatetime'] or ''} → {target} — {s['content']}")
            return {"text": "\n".join(lines)}
        except Exception as e:
            return {"text": f"查询失败：{e}"}


class DeleteReminderTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="delete_reminder",
            display_name="删除提醒",
            description="删除一个定时提醒。",
            parameters={
                "type": "object",
                "properties": {"reminder_id": {"type": "integer", "description": "提醒编号（#id）"}},
                "required": ["reminder_id"],
            },
            silent=True, final=True,
        )

    def execute(self, args: dict) -> dict:
        try:
            result = _call("DELETE", f"/{args['reminder_id']}")
            if result and result.get("code") == 200:
                return {"text": "提醒已删除"}
            return {"text": f"删除失败：{result}"}
        except Exception as e:
            return {"text": f"删除失败：{e}"}


registry.register(AddReminderTool())
registry.register(ListRemindersTool())
registry.register(DeleteReminderTool())
