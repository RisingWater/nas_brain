"""brain_services API 契约"""
from pydantic import BaseModel
from typing import Any, Dict
from src.common.schemas.agent_request import AgentRequest


class AgentResponse(BaseModel):
    code: int = 200
    data: Dict[str, Any] = {}
    message: str = "ok"


class AgentRequestWrapper(BaseModel):
    """接收 AgentRequest 的包装（兼容直接传 AgentRequest）"""
    request: AgentRequest
