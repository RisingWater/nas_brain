"""brain_services — 接收网关请求的路由

流程：
1. 收到 AgentRequest → 立即返回 200（"已收到"）
2. 消息入队到该用户的 UserProcessor（处理线程串行处理，多条 @ 合并）
3. 处理完成后由 UserProcessor 推送回复到 gateway
"""
import logging
from fastapi import APIRouter
from ..schema.brain_schema import AgentResponse
from src.common.schemas.agent_request import AgentRequest
from ..stats import stats
from ..user_processor import manager

logger = logging.getLogger("brain_services")

router = APIRouter()


@router.post("", response_model=AgentResponse)
async def receive_request(req: AgentRequest):
    """接收 AgentRequest，入队到用户处理器，立即返回"""
    logger.info("收到请求: id=%s user=%s type=%s content=%.50s",
                req.request_id, req.user_id, req.content_type.value, req.content or "")
    logger.info("[DEBUG] agent.py 收到 metadata: %s", dict(req.metadata or {}))

    # 入队（同一用户的消息由 UserProcessor 处理线程串行处理）
    manager.get_processor(req.user_id).enqueue(req)

    # 立即返回"已收到"
    return AgentResponse(data={
        "request_id": req.request_id,
        "text": "收到",
        "received": True,
    })


@router.get("/stats")
def get_stats():
    """返回统计信息"""
    return stats.get_stats()
