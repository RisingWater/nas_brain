"""语音合成与播放路由 — 接口前缀 /api/speak"""
import base64
import logging
import requests as _req
import tempfile
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
    request_id: str = Field("", description="链路追踪 ID")


def _play_via_voice_gateway(wav_data: bytes, sample_rate: int = 24000, request_id: str = ""):
    """将 WAV 音频发到 voice_gateway 播放，同步阻塞到播完"""
    url = cfg.get_service_url("voice_gateway", "/api/voice/play-wav")
    encoded = base64.b64encode(wav_data).decode("ascii")
    try:
        resp = _req.post(url, json={"data": encoded, "sample_rate": sample_rate, "request_id": request_id}, timeout=120)
        if resp.status_code != 200:
            logger.warning("voice_gateway 播放返回 %s: %s", resp.status_code, resp.text)
            return False
        return True
    except _req.exceptions.ConnectionError:
        logger.error("voice_gateway 不可用，播放失败")
        return False


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
    """合成文本并返回 WAV 数据（不回调 voice_gateway，由调用方自行播放）"""
    if not engine.is_ready:
        raise HTTPException(503, "TTS 引擎未就绪（TTS_URL 未配置）")

    logger.warning(f"开始tts: {req.text}")
    result = engine.synthesize_wav(req.text, req.voice, use_cache=True)
    if result is None:
        raise HTTPException(502, "语音合成失败")

    wav_data = result["data"]
    sample_rate = 24000  # Edge TTS 默认 24kHz

    if cfg.SINGLETON:
        # 单机模式：保存到临时文件，返回路径
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(wav_data)
        tmp.close()
        return {
            "code": 200,
            "data": {"file_path": tmp.name, "sample_rate": sample_rate, "from_cache": result["from_cache"]},
            "message": "ok",
        }
    else:
        # 多机模式：base64 编码返回
        encoded = base64.b64encode(wav_data).decode("ascii")
        return {
            "code": 200,
            "data": {"wav_base64": encoded, "sample_rate": sample_rate, "from_cache": result["from_cache"]},
            "message": "ok",
        }
