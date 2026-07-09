"""Processor 插件管理器 — 动态加载和热重载（同 tool / detector 模式）"""
import importlib
import logging
import sys
from pathlib import Path
from typing import List

from . import registry

logger = logging.getLogger("brain_services.processors.plugin_manager")

_PKG = "src.brain_services.processors"
_DIR = Path(__file__).parent.resolve()
_SKIP = {"__init__", "base", "plugin_manager"}


def discover() -> List[str]:
    modules = []
    for f in _DIR.iterdir():
        if f.suffix != ".py" or f.stem in _SKIP:
            continue
        modules.append(f.stem)
    return sorted(modules)


def load_all() -> int:
    count = 0
    for mod_name in discover():
        try:
            importlib.import_module(f".{mod_name}", _PKG.replace("/", "."))
            count += 1
        except Exception as e:
            logger.error("加载 processor 模块 %s 失败: %s", mod_name, e)
    logger.info("Processor 加载完成: %d 个模块, %d 个 processor", count, len(registry.get_all()))
    return count


def reload_all() -> int:
    for p in registry.get_all():
        registry.unregister(p.name)
    count = 0
    for mod_name in discover():
        try:
            full_name = f"{_PKG.replace('/', '.')}.{mod_name}"
            if full_name in sys.modules:
                importlib.reload(sys.modules[full_name])
            else:
                importlib.import_module(full_name)
            count += 1
        except Exception as e:
            logger.error("重载 processor 模块 %s 失败: %s", mod_name, e)
    loaded = len(registry.get_all())
    logger.info("Processor 重载完成: %d 个模块, %d 个 processor", count, loaded)
    return loaded
