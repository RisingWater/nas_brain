"""Home Assistant 空调控制工具"""
import os
import logging
import requests
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.home_assistant")

_HA_URL = os.getenv("HOME_ASSISTANT_URL", "")
_HA_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", "")
_HEADERS = {"Authorization": f"Bearer {_HA_TOKEN}", "Content-Type": "application/json"} if _HA_TOKEN else {}

_CN_DIGITS = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]


def _cn(n: int) -> str:
    if n <= 10:     return _CN_DIGITS[n] if n < 10 else "十"
    if n < 20:      return f"十{_CN_DIGITS[n - 10]}"
    if n < 100:
        tens = _CN_DIGITS[n // 10]
        ones = _CN_DIGITS[n % 10]
        return f"{tens}十{ones}" if n % 10 else f"{tens}十"
    hundreds = _CN_DIGITS[n // 100]
    rest = n % 100
    return f"{hundreds}百{_cn(rest)}" if rest else f"{hundreds}百"


def _call_service(domain: str, service: str, entity_id: str, data: dict = None):
    url = f"{_HA_URL}/api/services/{domain}/{service}"
    body = {"entity_id": entity_id}
    if data: body.update(data)
    resp = requests.post(url, json=body, headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _list_climate() -> list[dict]:
    resp = requests.get(f"{_HA_URL}/api/states", headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    return [{
        "entity_id": s["entity_id"],
        "name": s["attributes"].get("friendly_name", s["entity_id"]),
        "state": s["state"],
        "temperature": s["attributes"].get("temperature"),
        "hvac_modes": s["attributes"].get("hvac_modes", []),
        "min_temp": s["attributes"].get("min_temp"),
        "max_temp": s["attributes"].get("max_temp"),
    } for s in resp.json() if s["entity_id"].startswith("climate.") and s["state"] != "unavailable"]


def _fmt_ac(ac: dict) -> str:
    mode_cn = {"off": "关闭", "cool": "制冷", "heat": "制热", "auto": "自动", "fan_only": "送风", "dry": "除湿"}
    mode = mode_cn.get(ac["state"], ac["state"])
    s = f"{ac['name']}：{mode}"
    if ac.get("temperature"):
        s += f"，{ac['temperature']}°C"
    return s


def _find_entity(name: str) -> str | None:
    for ac in _list_climate():
        if name in ac["name"] or name in ac["entity_id"]:
            return ac["entity_id"]
    return None


class ListAcTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="list_ac",
            description="列出家中所有空调的名称、当前状态（开关/模式）和设定温度。",
            parameters={"type": "object", "properties": {}, "required": []},
            silent=True,
        )

    def execute(self, args: dict) -> dict:
        if not _HA_URL: return {"text": "Home Assistant 未配置（缺少 HOME_ASSISTANT_URL）"}
        try:
            acs = _list_climate()
            return {"text": "\n".join(_fmt_ac(a) for a in acs) if acs else "没有找到空调设备"}
        except Exception as e:
            return {"text": f"查询空调失败：{e}"}


class ControlAcTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="control_ac",
            description="控制指定的空调。必须先调 list_ac 获取空调名称。name 必填。支持开关、设置温度、切换模式。",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "空调名称，如'客厅'"},
                    "action": {"type": "string", "enum": ["on", "off", "set_temp", "set_mode"],
                               "description": "on=开机, off=关机, set_temp=设温度, set_mode=切换模式"},
                    "value": {"type": "string", "description": "set_temp 时填温度数字, set_mode 时填 cool/heat/auto"},
                },
                "required": ["action"],
            },
            silent=True, final=True,
        )

    def execute(self, args: dict) -> dict:
        if not _HA_URL: return {"text": "Home Assistant 未配置"}
        action, name, value = args.get("action"), args.get("name", ""), args.get("value", "")
        try:
            if not name:
                names = [a["name"] for a in _list_climate()]
                return {"text": f"请指定空调：{', '.join(names)}"}
            entity_id = _find_entity(name)
            if not entity_id: return {"text": f"未找到'{name}'"}
            friendly = name if name.endswith("空调") else f"{name}空调"
            if action == "on":
                _call_service("climate", "turn_on", entity_id)
                return {"text": f"{friendly}已开启"}
            elif action == "off":
                _call_service("climate", "turn_off", entity_id)
                return {"text": f"{friendly}已关闭"}
            elif action == "set_temp":
                if not value: return {"text": "请指定温度"}
                _call_service("climate", "set_hvac_mode", entity_id, {"hvac_mode": "cool"})
                _call_service("climate", "set_temperature", entity_id, {"temperature": float(value)})
                return {"text": f"{friendly}温度已设置为{_cn(int(float(value)))}度"}
            elif action == "set_mode":
                valid = {"cool", "heat", "auto", "dry", "fan_only"}
                if value not in valid: return {"text": f"无效模式，可选：{', '.join(sorted(valid))}"}
                _call_service("climate", "set_hvac_mode", entity_id, {"hvac_mode": value})
                return {"text": f"{friendly}已切换为{value}"}
            return {"text": f"未知操作: {action}"}
        except Exception as e:
            return {"text": f"空调控制失败：{e}"}


registry.register(ListAcTool())
registry.register(ControlAcTool())
