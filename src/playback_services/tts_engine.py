"""TTS 合成引擎 — 调用外部 EasyVoice API，支持缓存"""
import logging
import os
import subprocess
import tempfile
import requests
from pathlib import Path
from typing import Optional

from .tts_cache import TTSCache

logger = logging.getLogger("playback_services")

_TTS_URL = os.getenv("TTS_URL", "")
_TTS_CACHE_DIR = os.getenv("TTS_CACHE_DIR", "data/tts_cache")
_TTS_VOICE = os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural")


class TTSEngine:
    """TTS 合成引擎（HTTP 后端）"""

    def __init__(self):
        self.cache = TTSCache(_TTS_CACHE_DIR)
        self._ready = False

    def load(self):
        if not _TTS_URL:
            logger.warning("TTS_URL 未设置，播放服务以降级模式运行（仅缓存管理可用）")
            self._ready = False
            return
        self._ready = True
        logger.info("TTS 引擎就绪: %s", _TTS_URL)

    @property
    def is_ready(self) -> bool:
        return self._ready

    def synthesize_raw(self, text: str, voice: str = "") -> Optional[bytes]:
        """合成文本 → 原始 MP3 字节（来自 EasyVoice API）

        Returns:
            MP3 音频字节，失败返回 None
        """
        if not self._ready:
            logger.error("TTS 引擎未就绪")
            return None

        voice = voice or _TTS_VOICE
        payload = {
            "data": [{
                "text": text,
                "voice": voice,
                "rate": "0%",
                "pitch": "0Hz",
                "volume": "0%",
            }]
        }
        try:
            resp = requests.post(_TTS_URL, json=payload, timeout=30)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as e:
            logger.error("TTS API 调用失败: %s", e)
            return None

    def synthesize(self, text: str, voice: str = "", use_cache: bool = True) -> Optional[dict]:
        """合成文本 → 返回音频信息

        Args:
            text: 要合成的文本
            voice: 语音名称，空则用默认
            use_cache: 是否使用缓存

        Returns:
            {"format": "wav"|"mp3", "data": bytes, "path": Path|None, "from_cache": bool}
            失败返回 None
        """
        voice = voice or _TTS_VOICE
        backend = f"edge_{voice}"

        # 缓存命中
        if use_cache:
            cached = self.cache.get(text, backend)
            if cached is not None:
                return {
                    "format": "wav" if cached.suffix == ".wav" else "mp3",
                    "data": cached.read_bytes(),
                    "path": cached,
                    "from_cache": True,
                }

        # 请求 API
        raw_mp3 = self.synthesize_raw(text, voice)
        if raw_mp3 is None:
            return None

        # 保存到缓存（存原始 MP3，后续按需转 WAV）
        cached_path = self.cache.save(text, raw_mp3, ext=".mp3", backend=backend)

        return {
            "format": "mp3",
            "data": raw_mp3,
            "path": cached_path,
            "from_cache": False,
        }

    def synthesize_wav(self, text: str, voice: str = "", use_cache: bool = True) -> Optional[dict]:
        """合成文本 → 返回 WAV 格式音频（FFmpeg 转换）

        用于 speak 端点（PyAudio 需要 PCM WAV）
        """
        result = self.synthesize(text, voice, use_cache)
        if result is None:
            return None

        # 已经是 WAV 就直接返回
        if result["format"] == "wav":
            return result

        # MP3 → WAV 转换
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp.write(result["data"])
                mp3_path = tmp.name
            wav_path = mp3_path + ".wav"
            subprocess.run(
                ["ffmpeg", "-y", "-i", mp3_path, "-f", "wav", wav_path],
                capture_output=True, timeout=30,
            )
            with open(wav_path, "rb") as f:
                wav_data = f.read()
            os.unlink(mp3_path)
            os.unlink(wav_path)
            return {
                "format": "wav",
                "data": wav_data,
                "path": None,
                "from_cache": result["from_cache"],
            }
        except Exception as e:
            logger.error("FFmpeg 转换失败: %s", e)
            return result  # 降级返回 MP3


# 全局单例
engine = TTSEngine()
