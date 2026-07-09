"""dsm_detector — 开门检测插件（移植自 wechat_bot/detector/dsm_loop.py）"""
import logging
import threading
from .base import BaseDetector, DetectorContext, registry
from src.common.clients.kv_store import kv_store

logger = logging.getLogger("schedule_services.detector.dsm")

router_data = [
#    {
#        "name": "乔宝",
#        "detectors": [
#            {
#                "chatname": "学霸乔宝专项配套办公室",
#                "text": "王煜乔已经到家啦",
#                "type": "notify",
#            }
#        ]
#    },
#    {
#        "name": "顶子",
#        "detectors": [
#            {
#                "text": "王旭，欢迎回家",
#                "type": "audio_play"
#            }
#        ]
#    }
]


class DsmDetector(BaseDetector):
    """DSM 智能门禁开门检测

    轮询 DSM 开门记录，发现新开门 → 微信通知 + 语音播报
    """

    name = "dsm"
    interval = 180  # 默认 3 分钟
    _default_interval = 180

    def __init__(self):
        super().__init__()
        self._dsmxp = None  # 懒加载
        self._restore_timer = None

    def _get_dsmxp(self):
        if self._dsmxp is None:
            from src.common.clients.dsmxp import DSMSmartDoorAPI
            self._dsmxp = DSMSmartDoorAPI()
        return self._dsmxp

    def set_interval(self, interval: int):
        """临时调整检测间隔（外部可调用）"""
        old_interval = self._interval
        logger.info("DSM 间隔从 %ds 临时调整为 %ds，10分钟后恢复", old_interval, interval)
        self._interval = interval

        if self._restore_timer:
            self._restore_timer.cancel()

        def restore():
            self._interval = self._default_interval
            logger.info("DSM 间隔已恢复为默认值 %ds", self._default_interval)
            self._restore_timer = None

        self._restore_timer = threading.Timer(600, restore)
        self._restore_timer.daemon = True
        self._restore_timer.start()

    def process_loop(self, ctx: DetectorContext):
        try:
            dsmxp = self._get_dsmxp()
            loglist = dsmxp.get_log()
            send_msg = False

            for log in loglist:
                name = log.get("name")
                timestamp = log.get("timestamp")
                config_key = f"DSM_LOG_{timestamp}_{name}"

                if not kv_store.exists(config_key):
                    logger.info("发现新开门记录: %s %s", name, timestamp)

                    for route in router_data:
                        if route["name"] == "*" or route["name"] == name:
                            for detector in route["detectors"]:
                                if detector["type"] == "notify":
                                    msg = f"🎉🎉🎉 {name} 于 {timestamp.split(' ')[1]} 到家啦"
                                    ctx.send_wechat(detector["chatname"], msg)
                                    if detector.get("text"):
                                        ctx.speak_voice(detector["text"])
                                    send_msg = True
                                    break
                                elif detector["type"] == "audio_play":
                                    ctx.speak_voice(detector["text"])
                                    send_msg = True
                                    break
                    kv_store.set(config_key, "1", namespace="dsm")

            if send_msg and self._interval != self._default_interval:
                self._interval = self._default_interval
                logger.info("DSM 检测间隔已恢复")
                if self._restore_timer:
                    self._restore_timer.cancel()
                    self._restore_timer = None

        except Exception as e:
            logger.error("DSM 检测异常: %s", e, exc_info=True)


registry.register(DsmDetector())
