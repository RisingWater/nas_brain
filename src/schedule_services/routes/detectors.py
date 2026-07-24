"""Detector 管理 API — 列表/重载/禁用/配置"""
import json
import logging
from fastapi import APIRouter, HTTPException
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


# ---- 配置相关 ----

@router.get("/{name}/config-schema")
def get_detector_config_schema(name: str):
    """获取 detector 配置的 JSON Schema"""
    d = registry.get(name)
    if not d:
        raise HTTPException(404, f"detector '{name}' 不存在")
    schema = d.get_config_schema()
    _inline_refs(schema)
    _resolve_x_source(schema)
    return {"code": 200, "data": schema, "message": "ok"}


@router.get("/{name}/config")
def get_detector_config(name: str):
    """获取 detector 当前配置"""
    d = registry.get(name)
    if not d:
        raise HTTPException(404, f"detector '{name}' 不存在")
    return {"code": 200, "data": d.load_config(), "message": "ok"}


@router.put("/{name}/config")
def save_detector_config(name: str, body: dict):
    """保存 detector 配置"""
    d = registry.get(name)
    if not d:
        raise HTTPException(404, f"detector '{name}' 不存在")
    ok = d.save_config(body)
    if ok:
        d.load_config()  # 同步到实例变量（interval 等）
    return {"code": 200, "data": {"saved": ok}, "message": "ok" if ok else "保存失败"}


def _inline_refs(node: dict, defs: dict | None = None):
    """递归展开 JSON Schema 中的 $ref 引用（如 #/$defs/XXX）"""
    if defs is None:
        defs = node.pop("$defs", {})
    if isinstance(node, dict):
        ref = node.get("$ref", "")
        if ref and ref.startswith("#/$defs/"):
            name = ref[len("#/$defs/"):]
            resolved = defs.get(name, {})
            node.clear()
            node.update(resolved)
            # 递归展开被引用节点里的 ref
            _inline_refs(node, defs)
        else:
            for v in node.values():
                _inline_refs(v, defs)
    elif isinstance(node, list):
        for item in node:
            _inline_refs(item, defs)


def _resolve_x_source(schema: dict):
    """解析 schema 中的 x_source 标记，替换为实际选项列表"""
    for prop in schema.get("properties", {}).values():
        source = prop.pop("x_source", None)
        if source == "wechat_names":
            names = _fetch_wechat_names()
            if prop.get("type") == "array":
                prop["items"]["enum"] = names
            else:
                prop["enum"] = names


def _fetch_wechat_names() -> list[str]:
    """从 db_services 获取所有非空 wechat_name"""
    import requests
    from src.common.utils import cfg
    url = cfg.get_service_url("db_services", "/api/users?limit=500")
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            users = resp.json().get("users", [])
            return sorted(set(
                u["wechat_name"] for u in users if u.get("wechat_name")
            ))
    except Exception as e:
        logger.warning("获取微信名列表失败: %s", e)
    return []
