"""主动发言 — 测试触发端点"""
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter

logger = logging.getLogger("brain_services")

router = APIRouter()

_engine = None


def set_engine(engine):
    global _engine
    _engine = engine


class TriggerRequest(BaseModel):
    user_id: str = Field(..., description="目标用户/群 user_id")
    wechat_name: str = Field(..., description="微信名称")
    prompt: str = Field(..., description="主动发言提示词")


@router.post("/ice-breaker/trigger")
def trigger_ice_breaker(req: TriggerRequest):
    """手动触发主动发言（测试用）"""
    if not _engine:
        return {"code": 503, "message": "引擎未就绪", "data": None}
    try:
        _engine.generate_and_send(req.user_id, req.wechat_name, req.prompt)
        return {"code": 200, "message": "已触发", "data": {}}
    except Exception as e:
        logger.error("主动发言测试触发失败: %s", e)
        return {"code": 500, "message": str(e), "data": None}
