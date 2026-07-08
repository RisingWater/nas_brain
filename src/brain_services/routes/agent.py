"""brain_services — 接收网关请求的路由"""
from fastapi import APIRouter
from ..schema.brain_schema import AgentResponse
from src.common.schemas.agent_request import AgentRequest

router = APIRouter()


@router.post("", response_model=AgentResponse)
async def receive_request(req: AgentRequest):
    """接收 AgentRequest，返回成功（后续扩展为实际处理）"""
    print(f"[brain_services] 收到请求: id={req.request_id}, "
          f"user={req.user_id}, type={req.content_type.value}, "
          f"content={req.content[:50] if req.content else ''}")
    return AgentResponse(data={
        "request_id": req.request_id,
        "received": True,
    })
