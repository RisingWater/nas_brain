"""voice_gateway — 语音播放端点（带互斥锁）"""
import asyncio
import logging
import requests as _req
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
from src.common.utils import cfg

logger = logging.getLogger("voice_gateway")

router = APIRouter()

# 互斥状态由 processor 管理，这里通过导入引用
_processor = None


def set_processor(proc):
    global _processor
    _processor = proc


def _set_ai_status(state: str, speaker: str = "", message: str = "", **extra):
    """通过 brain_services 设置 AI 状态"""
    try:
        url = cfg.get_service_url("brain_services", "/api/status/set")
        _req.post(url, json={"state": state, "speaker": speaker, "message": message, "extra": extra}, timeout=5)
    except Exception as e:
        logger.debug("设置状态失败: %s", e)


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, description="要播放的文字")
    request_id: str = Field("", description="链路追踪 ID")


@router.post("/speak")
async def speak(req: SpeakRequest):
    """播放语音（外部接口：文字→合成→播放，同步阻塞）"""
    if not _processor:
        raise HTTPException(503, "语音处理器未就绪")
    try:
        # 状态：说话中（带文字内容）
        _set_ai_status("speaking", message=req.text[:80])
        from src.common.utils.tracer import trace_event as _trace_event
        await asyncio.to_thread(_processor.play_sync, req.text, req.request_id)
        if req.request_id:
            _trace_event(req.request_id, "play_end")
        # 状态：空闲
        _set_ai_status("idle")
        return {"code": 200, "data": {"text": req.text}, "message": "播放完成"}
    except Exception as e:
        logger.error("播放失败: %s", e)
        _set_ai_status("idle")
        raise HTTPException(502, f"播放失败: {e}")


