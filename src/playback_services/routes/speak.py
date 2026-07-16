"""语音合成与播放路由 — 接口前缀 /api/speak"""
import base64
import logging
import requests as _req
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from ..tts_engine import engine
from src.common.utils import cfg

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


def _play_via_voice_gateway(wav_data: bytes, sample_rate: int = 24000):
    """将 WAV 音频发到 voice_gateway 播放，同步阻塞到播完"""
    url = cfg.get_service_url("voice_gateway", "/api/voice/play-wav")
    encoded = base64.b64encode(wav_data).decode("ascii")
    resp = _req.post(url, json={"data": encoded, "sample_rate": sample_rate}, timeout=120)
    if resp.status_code != 200:
        logger.warning("voice_gateway 播放返回 %s: %s", resp.status_code, resp.text)
        return False
    return True


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
    """合成文本并通过 voice_gateway 播放"""
    if not engine.is_ready:
        raise HTTPException(503, "TTS 引擎未就绪（TTS_URL 未配置）")

    result = engine.synthesize_wav(req.text, req.voice, use_cache=True)
    if result is None:
        raise HTTPException(502, "语音合成失败")

    sample_rate = 24000  # Edge TTS 默认 24kHz
    if req.sync:
        ok = _play_via_voice_gateway(result["data"], sample_rate)
        return {
            "code": 200 if ok else 502,
            "data": {"from_cache": result["from_cache"]},
            "message": "播放完成" if ok else "播放失败",
        }
    else:
        import threading
        threading.Thread(
            target=_play_via_voice_gateway,
            args=(result["data"], sample_rate),
            daemon=True,
        ).start()
        return {
            "code": 200,
            "data": {"from_cache": result["from_cache"]},
            "message": "正在播放",
        }
