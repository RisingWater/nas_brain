"""voice_gateway — 语音播放端点（主循环队列调度）"""
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

logger = logging.getLogger("voice_gateway")

router = APIRouter()

_processor = None


def set_processor(proc):
    global _processor
    _processor = proc


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, description="要播放的文字")
    request_id: str = Field("", description="链路追踪 ID")


@router.post("/speak")
async def speak(req: SpeakRequest):
    """播放语音（异步：加入队列，不阻塞 HTTP）"""
    if not _processor:
        raise HTTPException(503, "语音处理器未就绪")
    _processor.enqueue_play(req.text, req.request_id)
    return {"code": 200, "data": {}, "message": "已加入播放队列"}
