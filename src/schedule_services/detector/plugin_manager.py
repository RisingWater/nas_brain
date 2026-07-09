"""Detector 插件管理器 — 动态加载和热重载（与 tool plugin_manager 同模式）"""
import importlib
import logging
import os
import sys
from pathlib import Path
from typing import List

from .base import registry

logger = logging.getLogger("schedule_services.detector.plugin_manager")

_DETECTOR_PKG = "src.schedule_services.detector"
_DETECTOR_DIR = Path(__file__).parent.resolve()

# 排除基类和内置模块的扫描黑名单
_SKIP_MODULES = {"__init__", "base", "plugin_manager"}


def discover_detectors() -> List[str]:
    """扫描 detector 目录，找到所有插件模块"""
    modules = []
    for f in _DETECTOR_DIR.iterdir():
        if f.suffix != ".py":
            continue
        if f.stem in _SKIP_MODULES:
            continue
        modules.append(f.stem)
    return sorted(modules)


def load_detectors() -> int:
    """加载所有 detector 模块（导入即注册）"""
    count = 0
    for mod_name in discover_detectors():
        try:
            importlib.import_module(f".{mod_name}", _DETECTOR_PKG.replace("/", "."))
            count += 1
        except Exception as e:
            logger.error("加载 detector 模块 %s 失败: %s", mod_name, e)
    logger.info("Detector 加载完成: %d 个模块, %d 个 detector", count, len(registry.get_all()))
    return count


def reload_detectors() -> int:
    """热重载所有 detector"""
    for d in registry.get_all():
        registry.unregister(d.name)

    count = 0
    for mod_name in discover_detectors():
        try:
            full_name = f"{_DETECTOR_PKG.replace('/', '.')}.{mod_name}"
            if full_name in sys.modules:
                importlib.reload(sys.modules[full_name])
            else:
                importlib.import_module(full_name)
            count += 1
        except Exception as e:
            logger.error("重载 detector 模块 %s 失败: %s", mod_name, e)

    loaded = len(registry.get_all())
    logger.info("Detector 重载完成: %d 个模块, %d 个 detector", count, loaded)
    return loaded
