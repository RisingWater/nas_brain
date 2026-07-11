"""策略引擎管理 API — 手工触发中期记忆总结"""
import logging
from fastapi import APIRouter, HTTPException
from ..strategy.summarizer import summarizer

logger = logging.getLogger("brain_services")

router = APIRouter()


@router.post("/summarize/{user_id}")
def trigger_summarize(user_id: str):
    """立即对指定用户执行中期记忆总结"""
    try:
        # force=True 重新总结所有消息，window=0 全部包含不截断
        summarizer._summarize_user(user_id, window_minutes=0, force=True)
        return {"code": 200, "data": {"user_id": user_id}, "message": "总结完成"}
    except Exception as e:
        logger.error("手动总结失败: %s", e, exc_info=True)
        raise HTTPException(500, f"总结失败: {e}")
