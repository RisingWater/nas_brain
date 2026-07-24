"""dsm_detector — 开门检测插件（移植自 wechat_bot/detector/dsm_loop.py）"""
import json
import logging
import threading
from typing import Literal
from pydantic import BaseModel, Field

from .base import BaseDetector, DetectorContext, registry
from src.common.clients.kv_store import kv_store

logger = logging.getLogger("schedule_services.detector.dsm")

class DsmRule(BaseModel):
    name: str = Field(
        ..., title="姓名",
        description="门禁日志中的人名，支持 * 通配",
    )
    notify_type: Literal["wechat", "voice"] = Field(
        "wechat", title="通知方式",
        description="wechat=微信群通知+语音, voice=仅语音播报",
    )
    chatname: str = Field(
        "", title="微信群",
        description="wechat 方式时需要填写",
    )
    text: str = Field(
        "", title="播报文字",
    )


_default_rules = [
    DsmRule(name="乔宝", notify_type="wechat", chatname="学霸乔宝专项配套办公室", text="王煜乔已经到家啦"),
    DsmRule(name="顶子", notify_type="voice", text="王旭，欢迎回家"),
]


class DsmConfig(BaseModel):
    interval: int = Field(
        180, title="运行间隔（秒）", ge=60,
        description="每隔多少秒查询一次开门记录",
    )
    rules: list[DsmRule] = Field(
        default=_default_rules,
        title="检测规则",
        description="配置每条规则：匹配的姓名、通知方式、播报内容",
    )


class DsmDetector(BaseDetector):
    """DSM 智能门禁开门检测

    轮询 DSM 开门记录，发现新开门 → 微信通知 / 语音播报
    """

    name = "dsm"
    interval = 180  # 默认 3 分钟
    ConfigModel = DsmConfig
    _default_interval = 180

    def __init__(self):
        super().__init__()
        self._interval = self.interval
        self._rules: list[dict] = [r.model_dump() for r in _default_rules]
        self._dsmxp = None
        self._restore_timer = None

    def load_config(self) -> dict:
        cfg = super().load_config()
        self.interval = cfg.get("interval", self.interval)
        # 用保存的规则覆盖，校验后回退到默认
        saved = cfg.get("rules", None)
        if saved and isinstance(saved, list):
            self._rules = saved
        else:
            self._rules = [r.model_dump() for r in _default_rules]
        return cfg

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

                    for rule in self._rules:
                        if rule["name"] != "*" and rule["name"] != name:
                            continue
                        rtype = rule.get("notify_type", rule.get("type", "wechat"))
                        text = rule.get("text", "")

                        if rtype == "wechat":
                            chatname = rule.get("chatname", "")
                            if chatname:
                                msg = f"🎉🎉🎉 {name} 于 {timestamp.split(' ')[1]} 到家啦"
                                ctx.send_wechat(chatname, msg)
                            if text:
                                ctx.speak_voice(text)
                        elif rtype == "voice":
                            if text:
                                ctx.speak_voice(text)
                        send_msg = True

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
