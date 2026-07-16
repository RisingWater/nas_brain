"""语音网关 — 音频录制管理（pyaudio + Silero VAD）"""
import os
import wave
import time
import logging
import numpy as np
import pyaudio
from datetime import datetime

logger = logging.getLogger("voice_gateway.audio_manager")

RECORD_SAMPLE_RATE = 16000
RECORD_CHANNELS = 1
RECORD_WIDTH = 2  # 16-bit
FRAMES_PER_BUFFER = 512
_RECORD_DIR = os.getenv("RECORD_DIR", "data/recordings")


class AudioManager:
    """音频录制管理器（pyaudio + Silero VAD）"""

    def __init__(self):
        self._pa = pyaudio.PyAudio()
        self._vad_model = None
        self._stream = None

    def _get_vad(self):
        """懒加载 Silero VAD 模型"""
        if self._vad_model is None:
            try:
                from silero_vad import load_silero_vad, get_speech_timestamps
                self._vad_model = load_silero_vad()
                self._get_speech_timestamps = get_speech_timestamps
                logger.info("Silero VAD 模型已加载")
            except ImportError:
                logger.warning("silero-vad 未安装，使用简单静音检测")
                self._vad_model = "simple"
        return self._vad_model

    def record(self, timeout_sec: int = 10, silence_ms: int = 800) -> np.ndarray:
        """录制音频直到静音或超时，返回 float32 numpy 数组（[-1, 1]）"""
        self._get_vad()
        logger.info("开始录音 (timeout=%ds, silence=%dms)", timeout_sec, silence_ms)

        stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=RECORD_CHANNELS,
            rate=RECORD_SAMPLE_RATE,
            input=True,
            frames_per_buffer=FRAMES_PER_BUFFER,
        )

        frames = []
        speech_frames = []  # 用于 VAD 检测的缓存
        silent_chunks = 0
        silence_chunks_needed = max(1, int(silence_ms / 1000))  # 每秒检一次，800ms→1次
        max_chunks = int(timeout_sec * RECORD_SAMPLE_RATE / FRAMES_PER_BUFFER)
        chunk_count = 0

        try:
            while chunk_count < max_chunks:
                data = stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False)
                frames.append(data)
                speech_frames.append(data)
                chunk_count += 1

                # 每秒做一次 VAD 检测
                if chunk_count % int(RECORD_SAMPLE_RATE / FRAMES_PER_BUFFER) == 0:
                    if self._vad_model != "simple":
                        try:
                            audio_int16 = np.frombuffer(b"".join(speech_frames), dtype=np.int16)
                            audio_float32 = audio_int16.astype(np.float32) / 32768.0
                            stamps = self._get_speech_timestamps(audio_float32, self._vad_model,
                                                                 sampling_rate=RECORD_SAMPLE_RATE)
                            if stamps:
                                silent_chunks = 0
                            else:
                                silent_chunks += 1
                        except Exception:
                            silent_chunks = 0
                    else:
                        # 简单检测：音量阈值
                        audio_int16 = np.frombuffer(b"".join(speech_frames), dtype=np.int16)
                        volume = np.abs(audio_int16).max()
                        if volume > 500:
                            silent_chunks = 0
                        else:
                            silent_chunks += 1
                    speech_frames = []

                    if silent_chunks >= max(1, silence_chunks_needed):
                        logger.debug("检测到静音，停止录音")
                        break

        finally:
            stream.stop_stream()
            stream.close()

        audio_data = b"".join(frames)
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        logger.info("录音完成: %d frames (%.1f 秒)", len(frames), len(frames) * FRAMES_PER_BUFFER / RECORD_SAMPLE_RATE)
        return audio_np

    def save_wav(self, audio: np.ndarray, filename: str = "") -> str:
        """保存 float32 numpy 为 WAV 文件，返回路径"""
        os.makedirs(_RECORD_DIR, exist_ok=True)
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{ts}.wav"
        filepath = os.path.join(_RECORD_DIR, filename)

        audio_int16 = (audio * 32768.0).astype(np.int16)
        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(RECORD_CHANNELS)
            wf.setsampwidth(RECORD_WIDTH)
            wf.setframerate(RECORD_SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())
        logger.debug("音频已保存: %s", filepath)
        return filepath

    def close(self):
        if self._pa:
            self._pa.terminate()
