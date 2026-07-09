"""battery_detector — 设备电量检测插件（移植自 wechat_bot/detector/battery_loop.py）"""
import logging
import time
from datetime import datetime, time as dt_time

from .base import BaseDetector, DetectorContext, registry

logger = logging.getLogger("schedule_services.detector.battery")

router_data = [
    {
        "chatname": "学霸乔宝专项配套办公室"
    },
]


class BatteryDetector(BaseDetector):
    """设备电量检测

    每天 20:30 检查设备电量，低电量 → 微信通知
    """

    name = "battery"
    interval = 3600  # 每小时检查一次，内部再按时间窗口控制

    def __init__(self):
        super().__init__()
        self._check_time = dt_time(20, 30)
        self._last_check_date = None
        self._low_battery_threshold = 30
        self._notified_devices: dict = {}

    def process_loop(self, ctx: DetectorContext):
        now = datetime.now()

        # 每天只在指定时间附近检查
        if now.time() < self._check_time:
            return
        if self._last_check_date == now.date():
            return

        # 到检查时间了
        self._last_check_date = now.date()
        logger.info("开始电池检测: %s", now.strftime("%Y-%m-%d %H:%M:%S"))

        try:
            from src.common.clients.qb_location import QBLocation
            qb = QBLocation()
            devices = qb.get_power()

            if not devices:
                logger.warning("未能获取设备电量")
                return

            low_devices = []
            for device in devices:
                device_id = device.get("device_id")
                device_name = device.get("device_name", "未知")
                power = device.get("power", 100)

                if power < self._low_battery_threshold:
                    last_power = self._notified_devices.get(device_id)
                    if last_power is None or power < last_power:
                        low_devices.append({"name": device_name, "power": power})
                        self._notified_devices[device_id] = power
                else:
                    self._notified_devices.pop(device_id, None)

            if low_devices:
                msg = "⚠️ 低电量提醒 ⚠️\n\n以下设备电量低于30%，请及时充电：\n\n"
                for d in low_devices:
                    msg += f"• {d['name']}: {d['power']}%\n"
                msg += "\n请及时充电以确保设备正常工作。"

                for route in router_data:
                    chatname = route.get("chatname")
                    if chatname:
                        ctx.send_wechat(chatname, msg)

        except Exception as e:
            logger.error("电量检测异常: %s", e, exc_info=True)


registry.register(BatteryDetector())
