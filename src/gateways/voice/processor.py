"""voice_gateway 核心 — 唤醒词 → VAD → 声纹 → STT → brain_services → TTS"""
import os
import uuid
import json
import time
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
        self._stt = STT()
        self._vp = VoiceprintEngine()

    # ---- 公开方法 ----

    def start(self):
        if self._running:
            return
        self._running = True

        # 1. 初始化 VAD（加载 Silero 模型）
        try:
            vad_init()
            # 触发 VAD 模型预加载
            from .audio_manager import AudioManager
            mgr = getattr(vad_init, '_mgr', None)
            from .vad import _audio_mgr
            if _audio_mgr:
                _audio_mgr._get_vad()
        except Exception as e:
            logger.warning("VAD 初始化失败: %s", e)

        # 2. 同步加载 STT 和声纹模型（全部就绪再开始检测唤醒词）
        try:
            self._stt.load()
            self._vp.load()
        except Exception as e:
            logger.error("模型加载失败: %s", e)

        # 3. 启动唤醒词检测
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
            logger.warning("TTS 成功: %s", resp.status_code, resp.text)
        except Exception as e:
            logger.error("TTS 播放失败: %s", e)
        finally:
            with self._lock:
                self._state = prev_state

    def play_wav(self, wav_data: bytes, sample_rate: int = 24000):
        """直接播放 WAV 数据（不走 play_sync，避免循环），播完恢复状态。"""
        logger.warning("play_wav 开始播放")
        prev_state = self.get_state()
        with self._lock:
            self._state = STATE_PLAYING
        try:
            import pyaudio as _pa
            pa = _pa.PyAudio()
            stream = pa.open(
                format=_pa.paInt16, channels=1, rate=sample_rate,
                output=True,
            )
           
            stream.write(wav_data)
            stream.stop_stream()
            stream.close()
            pa.terminate()
            logger.warning("play_wav 播放成功")
        except Exception as e:
            logger.error("WAV 播放失败: %s", e)
        finally:
            with self._lock:
                self._state = prev_state

    def get_state(self) -> int:
        with self._lock:
            return self._state

    def set_state(self, s: int):
        with self._lock:
            self._state = s

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

    def _get_vad_silence(self) -> int:
        """从 DB 获取静音判定毫秒数"""
        try:
            url = cfg.get_service_url("db_services", "/api/wakeword/vad-silence")
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json().get("silence_ms", 1600)
        except Exception:
            pass
        return 1600

    def _get_frame_samples(self) -> int:
        """从 DB 获取帧大小（每次 pyaudio 读取的采样数）"""
        try:
            url = cfg.get_service_url("db_services", "/api/wakeword/frame-samples")
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json().get("frame_samples", 3200)
        except Exception:
            pass
        return 3200

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
            silence_ms = self._get_vad_silence()
            wav_path = vad_record(timeout_sec=_VAD_TIMEOUT, silence_ms=silence_ms)
        except Exception as e:
            logger.error("VAD 录音失败: %s", e)
            self.set_state(STATE_IDLE)
            return

        self.set_state(STATE_PROCESSING)

        # 声纹识别（会移动音频文件到用户目录，返回新路径）
        user_id = "u_temp_voice"
        speaker = "未知用户"
        audio_path = wav_path  # 后续 STT 用这个路径（声纹可能已移动文件）
        try:
            user_id, speaker, audio_path = self._vp.detect(wav_path, wakeword_id)
        except Exception as e:
            logger.warning("声纹识别失败: %s", e)

        # STT 转文字（用声纹返回的路径，可能已被移动）
        text = ""
        try:
            text = self._stt.transcribe(audio_path)
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

    # ---- 主循环（自己控制采集，不用 WakeWordListener） ----

    def _run_loop(self):
        try:
            import pyaudio
            from livekit.wakeword import WakeWordModel
            # ---- ONNX Runtime 补丁（必须在任何 onnxruntime 使用前执行） ----
            import onnxruntime as ort
            _orig_init = ort.InferenceSession.__init__
            def _patched_init(self, path, sess_options=None, providers=None, **kw):
                if sess_options is None:
                    sess_options = ort.SessionOptions()
                sess_options.intra_op_num_threads = 1
                sess_options.inter_op_num_threads = 1
                sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
                sess_options.enable_mem_pattern = False
                sess_options.enable_cpu_mem_arena = False
                if providers is None:
                    providers = ["CPUExecutionProvider"]
                _orig_init(self, path, sess_options=sess_options, providers=providers, **kw)
            ort.InferenceSession.__init__ = _patched_init
        except ImportError:
            logger.error("livekit-wakeword 或 pyaudio 未安装")
            return

        if not os.path.exists(_MODEL_PATH):
            logger.error("唤醒词模型不存在: %s", _MODEL_PATH)
            return

        try:
            model = WakeWordModel(models=[_MODEL_PATH])
            threshold = self._get_threshold()
            frame_samples = self._get_frame_samples()
            buffer_frames = max(1, 32000 // frame_samples)  # ~2 秒的帧数

            pa = pyaudio.PyAudio()
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=frame_samples,
            )
            logger.info("唤醒词就绪，阈值=%.2f, 帧大小=%d, 缓冲帧数=%d",
                         threshold, frame_samples, buffer_frames)

            buffer: list[np.ndarray] = []
            last_detection_time = 0.0
            debounce = 1.0
            check_counter = 0

            while self._running:
                # 非 IDLE 状态（播放/录音/处理中）→ 清缓存跳过
                if self.get_state() != STATE_IDLE:
                    buffer.clear()
                    time.sleep(frame_samples / 16000)  # 等一帧的时间
                    continue

                # 每积累 80000 采样数检查一次帧大小变化（约 5 秒）
                check_counter += 1
                if check_counter * frame_samples >= 80000:
                    check_counter = 0
                    new_fs = self._get_frame_samples()
                    if new_fs != frame_samples:
                        logger.info("帧大小 %d → %d，重开音频流", frame_samples, new_fs)
                        stream.close()
                        frame_samples = new_fs
                        buffer_frames = max(1, 32000 // frame_samples)
                        buffer.clear()
                        stream = pa.open(
                            format=pyaudio.paInt16,
                            channels=1,
                            rate=16000,
                            input=True,
                            frames_per_buffer=frame_samples,
                        )

                # 读一帧音频
                data = stream.read(frame_samples, exception_on_overflow=False)
                frame = np.frombuffer(data, dtype=np.int16)
                buffer.append(frame)

                # 只保留最近 buffer_frames 帧
                while len(buffer) > buffer_frames:
                    buffer.pop(0)

                # 凑够 buffer_frames 帧才推理
                if len(buffer) < buffer_frames:
                    continue

                chunk = np.concatenate(buffer)
                scores = model.predict(chunk)
                best = max(scores.values()) if scores else 0.0

                now = time.time()
                if best >= threshold and (now - last_detection_time) >= debounce:
                    last_detection_time = now
                    logger.info("检测到唤醒词: score=%.4f", best)

                    # 保存唤醒音频
                    wakeword_id = self._save_wakeword_audio(chunk, 16000, best)
                    buffer.clear()  # 清缓存，避免重复检测

                    # 播"我在呢"（阻塞，等播完）
                    self.play_sync("我在呢")
                    threading.Thread(
                        target=self._voice_pipeline,
                        args=(wakeword_id,),
                        daemon=True,
                    ).start()

            stream.close()
            pa.terminate()

        except Exception as e:
            logger.error("唤醒词引擎异常: %s", e, exc_info=True)
