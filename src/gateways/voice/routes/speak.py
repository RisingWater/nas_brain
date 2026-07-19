"""voice_gateway — 语音播放端点（带互斥锁）"""
import asyncio
import base64
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
    request_id: str = Field("", description="链路追踪 ID")


class PlayWavRequest(BaseModel):
    data: str = Field(..., description="base64 编码的 WAV 音频数据")
    sample_rate: int = Field(24000, description="采样率")
    request_id: str = Field("", description="链路追踪 ID")


@router.post("/speak")
async def speak(req: SpeakRequest):
    """播放语音（外部接口：文字→合成→播放，同步阻塞）"""
    if not _processor:
        raise HTTPException(503, "语音处理器未就绪")
    try:
        from src.common.utils.tracer import trace_event as _trace_event
        await asyncio.to_thread(_processor.play_sync, req.text, req.request_id)
        if req.request_id:
            _trace_event(req.request_id, "play_end")
        return {"code": 200, "data": {"text": req.text}, "message": "播放完成"}
    except Exception as e:
        logger.error("播放失败: %s", e)
        raise HTTPException(502, f"播放失败: {e}")


@router.post("/play-wav")
async def play_wav(req: PlayWavRequest):
    """直接播放 WAV 音频数据（内部接口，不走 play_sync，避免循环）"""
    if not _processor:
        raise HTTPException(503, "语音处理器未就绪")
    try:
        wav_data = base64.b64decode(req.data)
        from src.common.utils.tracer import trace_event as _trace_event
        if req.request_id:
            _trace_event(req.request_id, "play_start")
        await asyncio.to_thread(_processor.play_wav, wav_data, req.sample_rate)
        if req.request_id:
            _trace_event(req.request_id, "play_end")
        return {"code": 200, "data": {"played": True}, "message": "播放完成"}
    except Exception as e:
        logger.error("WAV 播放失败: %s", e)
        raise HTTPException(502, f"WAV 播放失败: {e}")
