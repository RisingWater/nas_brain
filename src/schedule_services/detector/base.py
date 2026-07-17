"""Detector 插件系统 — BaseDetector + DetectorRegistry + DetectorContext"""
import logging
import time
from typing import Optional

logger = logging.getLogger("schedule_services.detector")


class DetectorContext:
    """给插件的上下文，封装服务间调用（不直接操作 wxauto / pyaudio）"""

    def send_wechat(self, who: str, msg: str):
        """发送微信消息 → wechat_gateway"""
        import requests
        from src.common.utils import cfg
        url = cfg.get_service_url("wechat_gateway", "/api/gateway/send-text")
        try:
            resp = requests.post(url, json={"who": who, "msg": msg}, timeout=10)
            resp.raise_for_status()
            logger.info("微信已发送 -> %s: %.30s", who, msg)
        except Exception as e:
            logger.error("微信发送失败 -> %s: %s", who, e)

    def speak_voice(self, text: str):
        """语音播报 → playback_services"""
        import requests
        from src.common.utils import cfg
        url = cfg.get_service_url("playback_services", "/api/speak/play")
        try:
            resp = requests.post(url, json={"text": text, "sync": False}, timeout=30)
            resp.raise_for_status()
            logger.info("语音已播报: %.30s", text)
        except Exception as e:
            logger.error("语音播报失败: %s", e)

    def get_config(self, key: str, default=None):
        """从环境变量读取配置"""
        import os
        return os.getenv(key, default)


class BaseDetector:
    """Detector 基类。子类需设置 name, interval 并实现 process_loop()"""

    name: str = ""
    interval: int = 60  # 运行间隔（秒）
    last_run: float = 0
    visible: bool = True  # 是否在管理页面显示
    enable: bool = True  # 是否启用（禁用后不运行）

    def __init__(self):
        if not self.name:
            self.name = self.__class__.__name__

    def process_loop(self, ctx: DetectorContext):
        """调度器每 tick 调用。由子类判断当前是否该执行。"""
        raise NotImplementedError


class DetectorRegistry:
    """Detector 注册表（单例，支持热加载）"""

    _instance: Optional["DetectorRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._detectors: dict[str, BaseDetector] = {}

    def register(self, detector: BaseDetector):
        self._detectors[detector.name] = detector
        logger.info("注册 detector: %s (interval=%ds)", detector.name, detector.interval)

    def unregister(self, name: str):
        self._detectors.pop(name, None)

    def get(self, name: str) -> Optional[BaseDetector]:
        return self._detectors.get(name)

    def get_all(self) -> list[BaseDetector]:
        """返回所有 detector（含不可见的），供调度器使用"""
        return list(self._detectors.values())

    def get_visible(self) -> list[BaseDetector]:
        """只返回 visible=True 的，供管理页面使用"""
        return [d for d in self._detectors.values() if d.visible]

    def clear(self):
        self._detectors.clear()

    def to_list(self) -> list[dict]:
        return [
            {
                "name": d.name,
                "interval": d.interval,
                "class": d.__class__.__name__,
                "enable": d.enable,
            }
            for d in self.get_visible()
        ]


# 全局单例
registry = DetectorRegistry()
