"""voice_gateway 核心 — 唤醒词 → VAD → 声纹 → STT → brain_services → TTS"""
import os
import uuid
import json
import logging
import threading
import wave
import requests
import numpy as np
from datetime import datetime
from src.common.utils import cfg
from .vad import record as vad_record, init as vad_init, close as vad_close
from .stt import STT
from .voiceprint import VoiceprintEngine

logger = logging.getLogger("voice_gateway")

_MODEL_PATH = os.getenv("WAKEWORD_MODEL", "data/models/paimeng_finetuned.onnx")
_WAKEWORD_DIR = os.getenv("WAKEWORD_DIR", "data/wakeword")
_DEFAULT_THRESHOLD = 0.7
_VAD_TIMEOUT = int(os.getenv("VAD_TIMEOUT_SEC", "10"))
_VAD_SILENCE = int(os.getenv("VAD_SILENCE_MS", "800"))

STATE_IDLE = 0
STATE_RECORDING = 1
STATE_PLAYING = 2
STATE_PROCESSING = 3


class VoiceProcessor:
    """语音处理器：唤醒词 → VAD → 声纹 → STT → brain → TTS"""

    def __init__(self):
        self._state = STATE_IDLE
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._listener = None
        self._stt = STT()
        self._vp = VoiceprintEngine()

    # ---- 公开方法 ----

    def start(self):
        if self._running:
            return
        self._running = True
        # 初始化 VAD
        try:
            vad_init()
        except Exception as e:
            logger.warning("VAD 初始化失败: %s", e)
        # 异步加载模型
        threading.Thread(target=self._load_models, daemon=True).start()
        # 启动唤醒词检测
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("语音处理器已启动")

    def stop(self):
        self._running = False
        vad_close()

    def play_sync(self, text: str):
        """同步播放语音。保存调用前状态，播完恢复。"""
        prev_state = self.get_state()
        with self._lock:
            self._state = STATE_PLAYING
        try:
            url = cfg.get_service_url("playback_services", "/api/speak/play")
            resp = requests.post(url, json={"text": text, "mode": "sync"}, timeout=60)
            if resp.status_code != 200:
                logger.warning("TTS 返回 %s: %s", resp.status_code, resp.text)
        except Exception as e:
            logger.error("TTS 播放失败: %s", e)
        finally:
            with self._lock:
                self._state = prev_state

    def get_state(self) -> int:
        with self._lock:
            return self._state

    def set_state(self, s: int):
        with self._lock:
            self._state = s

    # ---- 模型加载 ----

    def _load_models(self):
        """后台加载 STT 和声纹模型"""
        try:
            self._stt.load()
        except Exception as e:
            logger.error("STT 模型加载失败: %s", e)
        try:
            self._vp.load()
        except Exception as e:
            logger.error("声纹模型加载失败: %s", e)

    # ---- 唤醒词检测 ----

    def _get_threshold(self) -> float:
        try:
            url = cfg.get_service_url("db_services", "/api/wakeword/threshold")
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json().get("threshold", _DEFAULT_THRESHOLD)
        except Exception:
            pass
        return _DEFAULT_THRESHOLD

    def _save_wakeword_audio(self, audio: np.ndarray, sr: int, score: float) -> str:
        """保存唤醒音频，返回 (filepath, wakeword_id)"""
        os.makedirs(_WAKEWORD_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}_{score:.4f}.wav"
        filepath = os.path.join(_WAKEWORD_DIR, filename)
        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(audio.tobytes())

        wakeword_id = uuid.uuid4().hex[:12]
        try:
            url = cfg.get_service_url("db_services", "/api/wakeword/records")
            requests.post(url, json={
                "wakeword_id": wakeword_id,
                "file_path": filepath,
                "score": score,
            }, timeout=10)
        except Exception as e:
            logger.error("记录唤醒词失败: %s", e)

        logger.info("唤醒词: %s (score=%.4f, id=%s)", filepath, score, wakeword_id)
        return wakeword_id

    def _update_wakeword_category(self, wakeword_id: str, category: str):
        """更新唤醒词分类 positive/negative"""
        try:
            # 查找 record_id
            url = cfg.get_service_url("db_services", "/api/wakeword/records")
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                for item in items:
                    if item.get("wakeword_id") == wakeword_id:
                        rid = item["id"]
                        url2 = cfg.get_service_url("db_services", f"/api/wakeword/records/{rid}/category")
                        requests.put(url2, json={"category": category}, timeout=5)
                        break
        except Exception as e:
            logger.warning("更新唤醒词分类失败: %s", e)

    # ---- VAD + 声纹 + STT + brain_services 管线 ----

    def _voice_pipeline(self, wakeword_id: str):
        """VAD 录音 → 声纹 → STT → brain_services → TTS"""
        # VAD 录音
        self.set_state(STATE_RECORDING)
        try:
            wav_path = vad_record(timeout_sec=_VAD_TIMEOUT, silence_ms=_VAD_SILENCE)
        except Exception as e:
            logger.error("VAD 录音失败: %s", e)
            self.set_state(STATE_IDLE)
            return

        self.set_state(STATE_PROCESSING)

        # 声纹识别
        user_id = "u_temp_voice"
        speaker = "未知用户"
        try:
            user_id, speaker = self._vp.detect(wav_path, wakeword_id)
        except Exception as e:
            logger.warning("声纹识别失败: %s", e)

        # STT 转文字
        text = ""
        try:
            text = self._stt.transcribe(wav_path)
            logger.info("STT 结果: %s", text[:100])
        except Exception as e:
            logger.warning("STT 失败: %s", e)

        if not text.strip():
            logger.info("未检测到语音，跳过")
            self._update_wakeword_category(wakeword_id, "negative")
            self.set_state(STATE_IDLE)
            return

        # POST brain_services
        try:
            url = cfg.get_service_url("brain_services", "/api/agent-request")
            req_body = {
                "protocol": "voice",
                "request_id": f"voice_{uuid.uuid4().hex[:12]}",
                "chat_type": "voice",
                "user_id": user_id,
                "content_type": "text",
                "content": text,
                "metadata": {"wakeword_id": wakeword_id, "speaker": speaker},
            }
            resp = requests.post(url, json=req_body, timeout=120)
            if resp.status_code == 200:
                reply = resp.json().get("data", {}).get("text", "")
                if not reply:
                    logger.info("brain 返回空回复（可能 __SKIP__）")
                    self._update_wakeword_category(wakeword_id, "negative")
                    self.set_state(STATE_IDLE)
                    return

                # TTS 播放回复
                self._update_wakeword_category(wakeword_id, "positive")
                self.play_sync(reply)
            else:
                logger.warning("brain_services 返回 %s", resp.status_code)
        except Exception as e:
            logger.error("brain_services 调用失败: %s", e)

        self.set_state(STATE_IDLE)

    # ---- 唤醒词回调 ----

    def _on_detection(self, name: str, score: float, timestamp: float,
                      audio: np.ndarray, sr: int):
        if self.get_state() != STATE_IDLE:
            return
        logger.info("检测到唤醒词: score=%.4f", score)

        wakeword_id = self._save_wakeword_audio(audio, sr, score)

        # 播放"我在呢" → 阻塞直到播完
        self.play_sync("我在呢")

        # VAD → 声纹 → STT → brain → TTS（在新线程中运行）
        threading.Thread(
            target=self._voice_pipeline,
            args=(wakeword_id,),
            daemon=True,
        ).start()

    # ---- 主循环 ----

    def _run_loop(self):
        try:
            from livekit import wakeword as ww
        except ImportError:
            logger.error("livekit-wakeword 未安装")
            return

        if not os.path.exists(_MODEL_PATH):
            logger.error("唤醒词模型不存在: %s", _MODEL_PATH)
            return

        try:
            model = ww.WakeWordModel(_MODEL_PATH)
            threshold = self._get_threshold()
            logger.info("唤醒词就绪，阈值=%.2f", threshold)

            async def listen():
                listener = model.create_listener(
                    threshold=threshold,
                    debounce=1.0,
                    on_detection=self._on_detection,
                )
                self._listener = listener
                logger.info("唤醒词监听已启动")
                async with listener:
                    while self._running:
                        if self.get_state() != STATE_IDLE:
                            await asyncio.sleep(0.1)
                            continue
                        try:
                            detection = await asyncio.wait_for(
                                listener.wait_for_detection(), timeout=1.0
                            )
                        except asyncio.TimeoutError:
                            continue

            import asyncio
            asyncio.run(listen())

        except Exception as e:
            logger.error("唤醒词引擎异常: %s", e, exc_info=True)
