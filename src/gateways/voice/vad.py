"""语音网关 — VAD 录音封装"""
import logging
from .audio_manager import AudioManager

logger = logging.getLogger("voice_gateway.vad")

_audio_mgr: AudioManager | None = None


def init():
    global _audio_mgr
    _audio_mgr = AudioManager()


def record(timeout_sec: int = 10, silence_ms: int = 800) -> str:
    """录制音频直到静音或超时，返回 WAV 文件路径"""
    if not _audio_mgr:
        raise RuntimeError("AudioManager 未初始化")
    audio = _audio_mgr.record(timeout_sec=timeout_sec, silence_ms=silence_ms)
    return _audio_mgr.save_wav(audio)


def close():
    if _audio_mgr:
        _audio_mgr.close()
