"""service_manager API 路由"""
from fastapi import APIRouter, HTTPException
from ..manager import ServiceManager

router = APIRouter()

# 由 app.py 在初始化后注入
_manager: ServiceManager = None


def init(manager: ServiceManager):
    global _manager
    _manager = manager


@router.get("")
def list_services():
    """列出所有服务及其状态"""
    services = [svc.to_dict() for svc in _manager.services]
    return {"code": 200, "data": services, "message": "ok"}


@router.post("/{name}/start")
def start_service(name: str):
    """启动指定服务"""
    svc = _manager.get(name)
    if not svc:
        raise HTTPException(404, f"服务 '{name}' 不存在")
    if svc.status == "running":
        return {"code": 200, "message": f"'{name}' 已在运行"}
    ok = _manager.start(name)
    if not ok:
        raise HTTPException(500, f"启动 '{name}' 失败")
    return {"code": 200, "message": f"'{name}' 已启动"}


@router.post("/{name}/stop")
def stop_service(name: str):
    """停止指定服务"""
    svc = _manager.get(name)
    if not svc:
        raise HTTPException(404, f"服务 '{name}' 不存在")
    if svc.status == "stopped":
        return {"code": 200, "message": f"'{name}' 已停止"}
    ok = _manager.stop(name)
    if not ok:
        raise HTTPException(500, f"停止 '{name}' 失败")
    return {"code": 200, "message": f"'{name}' 已停止"}
