"""QB 设备位置/电量查询工具 — 通过 src.common.clients 实现，支持地图图片附件"""
import os
import logging
from src.common.clients.qb_location import QBLocation
from src.common.clients.amap import AmapAPI
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.location")


class YuqiaoLocationTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="get_yuqiao_location",
            description=(
                "查询煜乔（乔宝）的当前位置。返回设备名称、电量和详细地址。"
                "同时会生成一张地图位置图片，agent route 会根据请求来源决定是否发送。"
            ),
            parameters={"type": "object", "properties": {}, "required": []},
        )

    def execute(self, args: dict) -> dict:
        try:
            qb = QBLocation()
            locations = qb.get_location()
            if not locations:
                return {"text": "未找到设备"}
            yuqiao = next((d for d in locations if "乔宝" in d.get("device_name", "")), locations[0])
            name = yuqiao["device_name"]
            power = yuqiao["power"]
            addr = yuqiao.get("address", "地址获取失败")
            lat = yuqiao.get("latitude")
            lon = yuqiao.get("longitude")

            result = {"text": f"{name}（电量 {power}%）— {addr}", "files": []}

            # 生成地图图片
            if lat and lon:
                try:
                    amap = AmapAPI()
                    save_path = amap.get_static_map(
                        longitude=lon, latitude=lat,
                        zoom=16, size="600*600",
                    )
                    if save_path:
                        result["files"].append(save_path)
                except Exception as e:
                    logger.error("生成地图图片失败: %s", e)

            return result
        except Exception as e:
            return {"text": f"查询位置失败: {e}"}


class YuqiaoPowerTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="get_yuqiao_power",
            description="查询煜乔的通话器剩余电量，返回电量百分比。",
            parameters={"type": "object", "properties": {}, "required": []},
        )

    def execute(self, args: dict) -> dict:
        try:
            qb = QBLocation()
            devices = qb.get_power()
            if not devices:
                return {"text": "未找到设备"}
            yuqiao = next((d for d in devices if "乔宝" in d.get("device_name", "")), devices[0])
            return {"text": f"{yuqiao['device_name']} 当前电量 {yuqiao['power']}%"}
        except Exception as e:
            return {"text": f"查询电量失败: {e}"}


registry.register(YuqiaoLocationTool())
registry.register(YuqiaoPowerTool())
