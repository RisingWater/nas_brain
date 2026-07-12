"""voice_gateway — 语音播放端点（带互斥锁）"""
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

logger = logging.getLogger("voice_gateway")

router = APIRouter()

# 互斥状态由 processor 管理，这里通过导入引用
_processor = None


def set_processor(proc):
    global _processor
    _processor = proc


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, description="要播放的文字")


@router.post("/speak")
async def speak(req: SpeakRequest):
    """播放语音（同步阻塞，播完才返回）"""
    if not _processor:
        raise HTTPException(503, "语音处理器未就绪")
    try:
        _processor.play_sync(req.text)
        return {"code": 200, "data": {"text": req.text}, "message": "播放完成"}
    except Exception as e:
        logger.error("播放失败: %s", e)
        raise HTTPException(502, f"播放失败: {e}")
