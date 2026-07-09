"""QB 设备位置/电量查询工具 — 通过 src.common.clients.qb_location 实现"""
import logging
from src.common.clients.qb_location import QBLocation
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.location")


class YuqiaoLocationTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="get_yuqiao_location",
            description="查询煜乔的当前位置。返回设备名称、电量和详细地址。",
            parameters={"type": "object", "properties": {}, "required": []},
        )

    def execute(self, args: dict) -> str:
        try:
            qb = QBLocation()
            locations = qb.get_location()
            if not locations:
                return "未找到设备"
            # 优先找乔宝
            yuqiao = next((d for d in locations if "乔宝" in d.get("device_name", "")), locations[0])
            name = yuqiao["device_name"]
            power = yuqiao["power"]
            addr = yuqiao.get("address", "地址获取失败")
            return f"{name}（电量 {power}%）— {addr}"
        except Exception as e:
            return f"查询位置失败: {e}"


class YuqiaoPowerTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="get_yuqiao_power",
            description="查询煜乔的通话器剩余电量，返回电量百分比。",
            parameters={"type": "object", "properties": {}, "required": []},
        )

    def execute(self, args: dict) -> str:
        try:
            qb = QBLocation()
            devices = qb.get_power()
            if not devices:
                return "未找到设备"
            yuqiao = next((d for d in devices if "乔宝" in d.get("device_name", "")), devices[0])
            return f"{yuqiao['device_name']} 当前电量 {yuqiao['power']}%"
        except Exception as e:
            return f"查询电量失败: {e}"


registry.register(YuqiaoLocationTool())
registry.register(YuqiaoPowerTool())
