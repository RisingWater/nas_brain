"""门禁开门工具"""
import os
import logging
import requests
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.door")


class DoorTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="open_door",
            description="打开楼下门禁。调用后会自动打开单元楼的楼下门禁。",
            parameters={"type": "object", "properties": {}, "required": []},
            silent=True, final=True,
        )

    def execute(self, args: dict) -> str:
        url = os.getenv("DOOR_OPEN_URL", "")
        token = os.getenv("DOOR_OPEN_TOKEN", "")
        if not url:
            return "门禁开门未配置（缺少 DOOR_OPEN_URL）"
        headers = {
            "Authorization": f"bearer {token}",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
                           "AppleWebKit/605.1.15 Mobile/15E148"),
        }
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == "00000":
                logger.info("开门成功")
                return "楼下的门已打开"
            return f"开门失败: {data.get('msg', '未知错误')}"
        except requests.RequestException as e:
            return f"开门失败: {e}"


registry.register(DoorTool())
