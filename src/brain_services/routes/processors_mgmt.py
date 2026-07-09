"""Processor 管理 API — 列表/重载"""
import logging
from fastapi import APIRouter
from ..processors import registry
from ..processors.plugin_manager import load_all, reload_all

logger = logging.getLogger("brain_services")

router = APIRouter()


@router.get("")
def list_processors():
    return {"code": 200, "data": registry.to_list(), "message": "ok"}


@router.post("/load")
def load_all_processors():
    count = load_all()
    return {"code": 200, "data": {"loaded": count, "total": len(registry.get_all())}, "message": "ok"}


@router.post("/reload")
def reload_all_processors():
    count = reload_all()
    return {"code": 200, "data": {"reloaded": count, "total": len(registry.get_all())}, "message": "ok"}
