"""语音合成与播放路由 — 接口前缀 /api/speak"""
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from ..tts_engine import engine
from ..audio_manager import get_audio_manager

logger = logging.getLogger("playback_services")

router = APIRouter()


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="要合成的文本")
    voice: str = Field("", description="语音名称，空则用默认")
    use_cache: bool = Field(True, description="是否使用缓存")


class PlayRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="要播放的文本")
    voice: str = Field("", description="语音名称，空则用默认")
    sync: bool = Field(False, description="是否同步播放（阻塞到播完），默认异步返回")


@router.post("/synthesize")
async def synthesize(req: SynthesizeRequest):
    """合成文本 → 返回 WAV 音频文件"""
    if not engine.is_ready:
        raise HTTPException(503, "TTS 引擎未就绪（TTS_URL 未配置）")

    result = engine.synthesize_wav(req.text, req.voice, req.use_cache)
    if result is None:
        raise HTTPException(502, "语音合成失败")

    return Response(
        content=result["data"],
        media_type="audio/wav",
        headers={
            "X-Cache-Hit": str(result["from_cache"]).lower(),
            "Content-Disposition": 'attachment; filename="speak.wav"',
        },
    )


@router.post("/play")
async def play(req: PlayRequest):
    """合成文本并通过 pyaudio 播放"""
    if not engine.is_ready:
        raise HTTPException(503, "TTS 引擎未就绪（TTS_URL 未配置）")

    result = engine.synthesize_wav(req.text, req.voice, use_cache=True)
    if result is None:
        raise HTTPException(502, "语音合成失败")

    manager = get_audio_manager()

    if req.sync:
        manager.play_sync(result["data"])
        return {
            "code": 200,
            "data": {"from_cache": result["from_cache"]},
            "message": "播放完成",
        }
    else:
        manager.play_async(result["data"])
        return {
            "code": 200,
            "data": {"from_cache": result["from_cache"]},
            "message": "正在播放",
        }
