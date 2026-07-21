"""PS5 游戏控制工具 — 一键开关 PS5 + 联动小米电视"""
import os
import time
import logging
import requests
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.ps5_game")

_HA_URL = os.getenv("HOME_ASSISTANT_URL", "")
_HA_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", "")
_HEADERS = {"Authorization": f"Bearer {_HA_TOKEN}", "Content-Type": "application/json"} if _HA_TOKEN else {}
_MITV_PREFIX = "xiaomi_cn_mitv"


def _call_service(domain: str, service: str, entity_id: str, data: dict = None):
    url = f"{_HA_URL}/api/services/{domain}/{service}"
    body = {"entity_id": entity_id}
    if data: body.update(data)
    resp = requests.post(url, json=body, headers=_HEADERS, timeout=10)
    resp.raise_for_status()


def _press_button(entity_id: str):
    _call_service("button", "press", entity_id)


def _find_entity(prefix: str, keyword: str = "") -> str | None:
    resp = requests.get(f"{_HA_URL}/api/states", headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    for s in resp.json():
        eid = s["entity_id"]
        if eid.startswith(prefix) and keyword in eid:
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


class ControlPs5Tool(BaseTool):
    def __init__(self):
        super().__init__(
            name="control_ps5",
            display_name="控制PS5",
            parameters={
                "type": "object",
                "properties": {
                    "power": {"type": "boolean", "description": "true=开启PS5打游戏，false=关闭PS5"},
                },
                "required": ["power"],
            },
            silent=True, final=True,
        )

    def execute(self, args: dict) -> dict:
        if not _HA_URL: return {"text": "Home Assistant 未配置"}
        power = args["power"]
        try:
            if power:
                am = _is_audio_mode()
                if am is None: return {"text": "无法获取电视状态"}
                if am:
                    eid = _find_entity(f"button.{_MITV_PREFIX}", "turn_mode_off")
                    if not eid: return {"text": "没有找到电视按钮"}
                    _press_button(eid)
                    time.sleep(1)
                ps5 = _find_entity("switch.", "ps5") or _find_entity("media_player.", "playstation")
                if not ps5: return {"text": "未找到 PS5 设备"}
                _call_service(ps5.split(".")[0], "turn_on", ps5)
                time.sleep(3)
                tv = _find_entity(f"media_player.{_MITV_PREFIX}")
                if tv:
                    _call_service("media_player", "select_source", tv, {"source": "HDMI 1"})
                    return {"text": "PS5 已开启，电视已切换到 HDMI 1，开始享受游戏吧！"}
                return {"text": "PS5 已开启，请手动切换到 HDMI 1"}
            else:
                ps5 = _find_entity("switch.", "ps5") or _find_entity("media_player.", "playstation")
                if ps5:
                    _call_service(ps5.split(".")[0], "turn_off", ps5)
                eid = _find_entity(f"button.{_MITV_PREFIX}", "turn_mode_on")
                if eid: _press_button(eid)
                return {"text": "PS5 已关闭"}
        except Exception as e:
            return {"text": f"PS5 控制失败：{e}"}


registry.register(ControlPs5Tool())
