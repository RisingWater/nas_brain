"""系统音量控制工具（Linux PulseAudio / 占位）"""
import sys
import subprocess
import re
import logging
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.volume")

_SINK = "@DEFAULT_SINK@"

_CN_DIGITS = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]


def _cn(n: int) -> str:
    if n < 10:      return _CN_DIGITS[n]
    if n == 10:     return "十"
    if n < 20:      return f"十{_CN_DIGITS[n - 10]}"
    if n < 100:
        tens = _CN_DIGITS[n // 10]
        ones = _CN_DIGITS[n % 10]
        return f"{tens}十{ones}" if n % 10 else f"{tens}十"
    hundreds = _CN_DIGITS[n // 100]
    rest = n % 100
    return f"{hundreds}百{_cn(rest)}" if rest else f"{hundreds}百"


def _has_pulseaudio() -> bool:
    try:
        subprocess.run(["pactl", "--version"], capture_output=True, timeout=3)
        return True
    except Exception:
        return False


_HAS_PA = _has_pulseaudio()


def _get_volume() -> int:
    r = subprocess.run(["pactl", "get-sink-volume", _SINK], capture_output=True, text=True, timeout=5)
    m = re.search(r"(\d+)%", r.stdout)
    return int(m.group(1)) if m else 50


class GetVolumeTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="get_volume",
            description="获取当前扬声器音量百分比。",
            parameters={"type": "object", "properties": {}, "required": []},
            silent=True,
        )

    def execute(self, args: dict) -> str:
        if not _HAS_PA: return "音量控制仅支持 Linux PulseAudio"
        try:
            return f"当前音量 {_get_volume()}%"
        except Exception as e:
            return f"获取音量失败：{e}"


class SetVolumeTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="set_volume",
            description="设置扬声器音量。参数为百分比数字，如 50 表示 50%。",
            parameters={
                "type": "object",
                "properties": {"volume": {"type": "integer", "description": "音量百分比，0-200，如 50"}},
                "required": ["volume"],
            },
            silent=True, final=True,
        )

    def execute(self, args: dict) -> str:
        if not _HAS_PA: return "音量控制仅支持 Linux PulseAudio"
        vol = max(0, min(200, int(args["volume"])))
        try:
            subprocess.run(["pactl", "set-sink-volume", _SINK, f"{vol}%"],
                           capture_output=True, check=True, timeout=5)
            return f"音量已经设置为百分之{_cn(vol)}"
        except Exception as e:
            return f"设置音量失败：{e}"


if sys.platform != "win32":
    registry.register(GetVolumeTool())
    registry.register(SetVolumeTool())
