"""工具管理 API — 列表/重载"""
import logging
from fastapi import APIRouter
from ..tools import registry
from ..tools.plugin_manager import load_tools, reload_tools

logger = logging.getLogger("brain_services")

router = APIRouter()


@router.get("")
def list_tools():
    """列出所有已加载的工具"""
    tools = registry.to_list()
    return {"code": 200, "data": tools, "message": "ok"}


@router.get("/schemas")
def list_tool_schemas():
    """获取所有工具的 OpenAI function-calling schema"""
    schemas = registry.get_schemas()
    return {"code": 200, "data": schemas, "message": "ok"}


@router.post("/load")
def load_all_tools():
    """加载 tools 目录下的所有工具"""
    count = load_tools()
    return {"code": 200, "data": {"loaded": count, "total": len(registry.get_all())}, "message": "ok"}


@router.post("/reload")
def reload_all_tools():
    """热重载所有工具"""
    count = reload_tools()
    return {"code": 200, "data": {"reloaded": count, "total": len(registry.get_all())}, "message": "ok"}
