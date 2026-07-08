"""brain_services — 接收网关请求的路由"""
import logging
from fastapi import APIRouter
from ..schema.brain_schema import AgentResponse
from src.common.schemas.agent_request import AgentRequest

logger = logging.getLogger("brain_services")

router = APIRouter()


@router.post("", response_model=AgentResponse)
async def receive_request(req: AgentRequest):
    """接收 AgentRequest，返回成功（后续扩展为实际处理）"""
    logger.info("收到请求: id=%s user=%s type=%s content=%.50s",
                req.request_id, req.user_id, req.content_type.value, req.content or "")
    return AgentResponse(data={
        "request_id": req.request_id,
        "received": True,
    })
