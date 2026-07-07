"""service_manager API 路由"""
from fastapi import APIRouter, HTTPException
from ..manager import ServiceManager
from ..schema.services_schema import (
    ServiceListResponse, ServiceActionResponse, ServiceInfoResponse,
)

router = APIRouter()

_manager: ServiceManager = None


def init(manager: ServiceManager):
    global _manager
    _manager = manager


@router.get("", response_model=ServiceListResponse)
def list_services():
    """列出所有服务及其状态"""
    services = [ServiceInfoResponse(**svc.to_dict()) for svc in _manager.services]
    return ServiceListResponse(data=services)


@router.post("/{name}/start", response_model=ServiceActionResponse)
def start_service(name: str):
    """启动指定服务"""
    svc = _manager.get(name)
    if not svc:
        raise HTTPException(404, f"服务 '{name}' 不存在")
    if svc.status == "running":
        return ServiceActionResponse(message=f"'{name}' 已在运行")
    ok = _manager.start(name)
    if not ok:
        raise HTTPException(500, f"启动 '{name}' 失败")
    return ServiceActionResponse(message=f"'{name}' 已启动")


@router.post("/{name}/stop", response_model=ServiceActionResponse)
def stop_service(name: str):
    """停止指定服务"""
    svc = _manager.get(name)
    if not svc:
        raise HTTPException(404, f"服务 '{name}' 不存在")
    if svc.status == "stopped":
        return ServiceActionResponse(message=f"'{name}' 已停止")
    ok = _manager.stop(name)
    if not ok:
        raise HTTPException(500, f"停止 '{name}' 失败")
    return ServiceActionResponse(message=f"'{name}' 已停止")


@router.post("/{name}/restart", response_model=ServiceActionResponse)
def restart_service(name: str):
    """重启指定服务"""
    svc = _manager.get(name)
    if not svc:
        raise HTTPException(404, f"服务 '{name}' 不存在")
    _manager.stop(name)
    ok = _manager.start(name)
    if not ok:
        raise HTTPException(500, f"重启 '{name}' 失败")
    return ServiceActionResponse(message=f"'{name}' 已重启")
