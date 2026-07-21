"""长期记忆工具 — 文件存储，读写用户偏好/事实"""
import os
import logging
from datetime import datetime
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.memory")

_MEMORY_FILE = os.getenv("MEMORY_FILE", "data/memory.md")


def _read_raw() -> str:
    if not os.path.exists(_MEMORY_FILE):
        return "（暂无长期记忆）"
    with open(_MEMORY_FILE, encoding="utf-8") as f:
        return f.read().strip()


def _save_fact(fact: str) -> str:
    fact = fact.strip()
    if not fact:
        return "未提供要记录的内容"
    os.makedirs(os.path.dirname(_MEMORY_FILE) or ".", exist_ok=True)

    try:
        if os.path.exists(_MEMORY_FILE):
            with open(_MEMORY_FILE, encoding="utf-8") as f:
                if fact in f.read():
                    return f"已存在：{fact}"
    except Exception:
        pass

    with open(_MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"- {fact}\n")
    return f"已记住：{fact}"


class ReadMemoryTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="read_memory",
            display_name="读取记忆",
            description="读取长期记忆，获取已知的用户偏好、身份、房间归属等信息。",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            silent=True,
        )

    def execute(self, args: dict) -> dict:
        return {"text": _read_raw()}


class SaveMemoryTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="save_memory",
            display_name="保存记忆",
            description="向长期记忆追加一条新信息。当了解到用户的新偏好、身份、房间设备归属等时使用。每条记忆一行。",
            parameters={
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "要记录的事实，如'王旭的房间是主卧'"},
                },
                "required": ["fact"],
            },
            silent=True,
        )

    def execute(self, args: dict) -> dict:
        return {"text": _save_fact(args.get("fact", ""))}


registry.register(ReadMemoryTool())
registry.register(SaveMemoryTool())
