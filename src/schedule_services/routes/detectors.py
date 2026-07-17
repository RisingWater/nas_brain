"""Detector 管理 API — 列表/重载/禁用"""
import logging
from fastapi import APIRouter
from pydantic import BaseModel
from ..detector.base import registry
from ..detector.plugin_manager import load_detectors, reload_detectors

logger = logging.getLogger("schedule_services")

router = APIRouter()


class DetectorEnableRequest(BaseModel):
    enable: bool


@router.get("")
def list_detectors():
    """列出所有已加载的 detector"""
    return {"code": 200, "data": registry.to_list(), "message": "ok"}


@router.post("/load")
def load_all_detectors():
    """加载 detector 目录下的所有插件"""
    count = load_detectors()
    return {
        "code": 200,
        "data": {"loaded": count, "total": len(registry.get_all())},
        "message": "ok",
    }


@router.put("/{name}/enable")
def enable_detector(name: str, body: DetectorEnableRequest):
    """启用或禁用指定 detector"""
    d = registry.get(name)
    if not d:
        return {"code": 404, "data": None, "message": f"detector '{name}' 不存在"}
    d.enable = body.enable
    return {"code": 200, "data": {"name": name, "enable": d.enable}, "message": "ok"}


@router.post("/reload")
def reload_all_detectors():
    """热重载所有 detector"""
    count = reload_detectors()
    return {
        "code": 200,
        "data": {"reloaded": count, "total": len(registry.get_all())},
        "message": "ok",
    }
