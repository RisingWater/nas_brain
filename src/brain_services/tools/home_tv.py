"""Home Assistant 小米电视控制工具"""
import os
import logging
import requests
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.home_tv")

_HA_URL = os.getenv("HOME_ASSISTANT_URL", "")
_HA_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", "")
_HEADERS = {"Authorization": f"Bearer {_HA_TOKEN}", "Content-Type": "application/json"} if _HA_TOKEN else {}
_MITV_PREFIX = "xiaomi_cn_mitv"


def _press_button(entity_id: str):
    resp = requests.post(
        f"{_HA_URL}/api/services/button/press",
        json={"entity_id": entity_id}, headers=_HEADERS, timeout=10,
    )
    resp.raise_for_status()


def _find_tv_button(keyword: str) -> str | None:
    resp = requests.get(f"{_HA_URL}/api/states", headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    for s in resp.json():
        eid = s["entity_id"]
        if eid.startswith(f"button.{_MITV_PREFIX}") and keyword in eid:
            return eid
    return None


def _is_audio_mode() -> bool | None:
    resp = requests.get(f"{_HA_URL}/api/states", headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    for s in resp.json():
        eid = s["entity_id"]
        if eid.startswith("switch.") and _MITV_PREFIX in eid and "is_on" in eid:
            return s["state"] == "on"
    return None


class GetTvStateTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="get_tv_state",
            description="查询电视当前状态（打开/音响模式/关闭）。",
            parameters={"type": "object", "properties": {}, "required": []},
            silent=True,
        )

    def execute(self, args: dict) -> str:
        if not _HA_URL: return "Home Assistant 未配置"
        try:
            am = _is_audio_mode()
            if am is None: return "无法获取电视状态"
            return "电视处于音响模式（屏幕关闭）" if am else "电视已打开（退出音响模式）"
        except Exception as e:
            return f"查询失败：{e}"


class ControlTvTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="control_tv",
            description="控制小米电视。开=退出音响模式，关=进入音响模式。调用前先调 get_tv_state。",
            parameters={
                "type": "object",
                "properties": {"action": {"type": "string", "enum": ["on", "off"], "description": "on=开机, off=关机"}},
                "required": ["action"],
            },
            silent=True, final=True,
        )

    def execute(self, args: dict) -> str:
        if not _HA_URL: return "Home Assistant 未配置"
        try:
            if args["action"] == "on":
                eid = _find_tv_button("turn_mode_off")
                if not eid: return "没有找到电视开关按钮"
                _press_button(eid)
                return "电视已打开"
            else:
                eid = _find_tv_button("turn_mode_on")
                if not eid: return "没有找到电视音响模式按钮"
                _press_button(eid)
                return "电视已关闭（进入音响模式）"
        except Exception as e:
            return f"电视控制失败：{e}"


registry.register(GetTvStateTool())
registry.register(ControlTvTool())
