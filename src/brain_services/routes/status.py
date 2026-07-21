"""brain_services — AI 状态路由"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..status import ai_status, STATES

logger = logging.getLogger("brain_services.routes.status")

router = APIRouter()


class StatusSetRequest(BaseModel):
    state: str = Field(..., description="状态值")
    speaker: str = Field("", description="说话人")
    message: str = Field("", description="上下文文字")
    extra: dict = Field(default_factory=dict, description="额外数据")


@router.get("/status")
def get_status():
    """获取当前 AI 状态"""
    return ai_status.get()


@router.post("/status/set")
def set_status(req: StatusSetRequest):
    """设置 AI 状态（供其他服务调用）"""
    if req.state not in STATES:
        raise HTTPException(400, f"无效状态，可选: {', '.join(STATES)}")
    ai_status.set(req.state, speaker=req.speaker, message=req.message, **req.extra)
    logger.info("状态 → %s (speaker=%s, message=%.30s)", req.state, req.speaker, req.message)
    return {"success": True, "state": req.state}
