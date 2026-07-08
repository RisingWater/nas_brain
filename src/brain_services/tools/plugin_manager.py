"""工具插件管理器 — 动态加载和热重载"""
import importlib
import logging
import os
import sys
from pathlib import Path
from typing import List

from . import registry

logger = logging.getLogger("brain_services.tools.plugin_manager")

_TOOLS_PKG = "src.brain_services.tools"
_TOOLS_DIR = Path(__file__).parent.resolve()


def discover_tools() -> List[str]:
    """扫描 tools 目录，找到所有工具模块（排除 __init__ 和 plugin_manager）"""
    modules = []
    for f in _TOOLS_DIR.iterdir():
        if f.suffix != ".py":
            continue
        if f.stem.startswith("__") or f.stem == "plugin_manager":
            continue
        modules.append(f.stem)
    return sorted(modules)


def load_tools() -> int:
    """加载所有工具模块（导入即注册）"""
    count = 0
    for mod_name in discover_tools():
        try:
            importlib.import_module(f".{mod_name}", _TOOLS_PKG.replace("/", "."))
            count += 1
        except Exception as e:
            logger.error("加载工具模块 %s 失败: %s", mod_name, e)
    logger.info("工具加载完成: %d 个模块, %d 个工具", count, len(registry.get_all()))
    return count


def reload_tools() -> int:
    """热重载所有工具"""
    old_names = [t.name for t in registry.get_all()]
    for name in old_names:
        registry.unregister(name)

    count = 0
    for mod_name in discover_tools():
        try:
            full_name = f"{_TOOLS_PKG.replace('/', '.')}.{mod_name}"
            if full_name in sys.modules:
                importlib.reload(sys.modules[full_name])
            else:
                importlib.import_module(full_name)
            count += 1
        except Exception as e:
            logger.error("重载工具模块 %s 失败: %s", mod_name, e)

    loaded = len(registry.get_all())
    logger.info("工具重载完成: %d 个模块, %d 个工具", count, loaded)
    return loaded
