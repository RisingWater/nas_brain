"""voice_gateway 核心 — 唤醒词 → VAD → 声纹 → STT → brain_services → TTS"""
import os
import uuid
import json
import time
import logging
import threading
import queue
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
        self._play_queue: queue.Queue = queue.Queue()
        self._wakeword_stream = None  # pyaudio 输入流，仅 IDLE 状态使用

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

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """用。！？拆分句子"""
        import re
        parts = re.split(r'(。|！|？|\.|!|\?)', text)
        sentences = []
        buf = ""
        for part in parts:
            if part in "。！？.!?":
                sentences.append(buf + part)
                buf = ""
            else:
                buf += part
        if buf.strip():
            sentences.append(buf)
        return [s.strip() for s in sentences if s.strip()]

    def _play_audio(self, pa, wav_data: bytes, last_sentence: bool = False):
        """pyaudio 播放单句，从 WAV 头读取格式参数，分块写入（200ms/块）"""
        import pyaudio as _pa, wave as _wave, io as _io
        import time
        import traceback
        
        stream = None
        try:
            # 解析 WAV 头
            with _wave.open(_io.BytesIO(wav_data), "rb") as _wf:
                sr = _wf.getframerate()
                channels = _wf.getnchannels()
                sw = _wf.getsampwidth()
            
            fmt_map = {1: _pa.paInt8, 2: _pa.paInt16}
            fmt = fmt_map.get(sw, _pa.paInt16)
            
            # 裸 PCM 数据
            pcm = wav_data[44:] if len(wav_data) > 44 else wav_data
            frame_size = sw * channels
            chunk_frames = int(sr * 0.2)
            chunk_bytes = chunk_frames * frame_size
            
            # 打开流
            stream = pa.open(format=fmt, channels=channels, rate=sr, output=True, frames_per_buffer=chunk_frames)
            
            # 分块写入
            audio_duration = len(pcm) / (sw * channels * sr)  # 音频总时长（秒）
            offset = 0
            data_len = len(pcm)
            write_start = time.time()
            while offset < data_len:
                end = min(offset + chunk_bytes, data_len)
                stream.write(pcm[offset:end])
                offset = end
            
            # 直接 sleep 剩余播放时间，避免 stream.is_active() 死等
            remaining = max(0, audio_duration - (time.time() - write_start))
            if remaining > 0:
                time.sleep(remaining + 0.05)
            stream.stop_stream()
                
        except Exception as e:
            # ✅ 捕获所有异常并输出详细堆栈
            logger.error(f"[ERROR] _play_audio 异常: {e}")
            print(traceback.format_exc())
            # 不重新抛出，让 finally 执行清理
            
        finally:
            if stream:
                try:
                    stream.close()
                    if not last_sentence:
                        time.sleep(0.2)
                except Exception as e:
                    # ✅ 捕获关闭流时的异常
                    print(f"[ERROR] 关闭 stream 异常: {e}")
                    print(traceback.format_exc())

    def enqueue_play(self, text: str, request_id: str = ""):
        """外部接口：将播放请求加入队列，HTTP 不阻塞。"""
        self._play_queue.put((text, request_id))

    def _set_ai_status(self, state: str, speaker: str = "", message: str = "", **extra):
        """通过 brain_services 设置 AI 状态"""
        try:
            url = cfg.get_service_url("brain_services", "/api/status/set")
            requests.post(url, json={"state": state, "speaker": speaker, "message": message, "extra": extra}, timeout=0.2)
        except Exception as e:
            logger.debug("设置状态失败: %s", e)

    def play_sync(self, text: str, request_id: str = ""):
        """同步播放语音：拆句 → 逐句 TTS → 边合成边播放。全程 STATE_PLAYING。

        只从 _run_loop 调用（播放队列或唤醒词流程），无需忙等。
        """
        self._set_ai_status("speaking", message=text[:80])
        logger.warning(f"play_sync 开始播放 {text}")
        import pyaudio as _pa
        _pa_instance = _pa.PyAudio()
        from src.common.utils.tracer import trace_event as _trace_event
        try:
            sentences = self._split_sentences(text)
            if not sentences:
                return

            inner_queue: queue.Queue = queue.Queue()
            done_event = threading.Event()
            logger.info("共 %d 句，开始流水线播放", len(sentences))

            # 消费者线程：逐条出队播放
            def _consumer():
                while True:
                    item = inner_queue.get()
                    if item is None:
                        break
                    wav, sr, last_sentence = item
                    dur = len(wav) / sr / 2  # 16bit mono
                    logger.warning("播放音频 %.1fs", dur)
                    t0 = time.time()
                    try:
                        self._play_audio(_pa_instance, wav, last_sentence)
                    except Exception as e:
                        logger.error("音频播放失败: %s", e)
                    logger.warning("播放结束 耗时%.2fs", time.time() - t0)
                done_event.set()

            consumer = threading.Thread(target=_consumer, daemon=True)
            consumer.start()

            # 生产者：逐句 TTS 合成，放入队列
            for idx, sentence in enumerate(sentences):
                logger.info("TTS 第%d句: %.40s", idx + 1, sentence)
                try:
                    url = cfg.get_service_url("playback_services", "/api/speak/play")
                    t0 = time.time()
                    resp = requests.post(
                        url, json={"text": sentence, "voice": "", "use_cache": True}, timeout=60,
                    )
                    t_tts = time.time() - t0
                    if resp.status_code != 200:
                        logger.warning("TTS 第%d句返回 %s: %s", idx + 1, resp.status_code, resp.text)
                        continue
                    body = resp.json()
                    data = body.get("data", {})

                    if "file_path" in data:
                        with open(data["file_path"], "rb") as f:
                            wav_data = f.read()
                        try:
                            os.unlink(data["file_path"])
                        except Exception:
                            pass
                    elif "wav_base64" in data:
                        import base64 as _b64
                        wav_data = _b64.b64decode(data["wav_base64"])
                    else:
                        continue

                    if idx == len(sentences) - 1:
                        last_sentence = True
                    else:
                        last_sentence = False

                    # 从 WAV 头读取真实采样率
                    import io as _io, wave as _wave
                    with _wave.open(_io.BytesIO(wav_data), "rb") as _wf:
                        sr = _wf.getframerate()
                    dur = len(wav_data) / sr / 2
                    logger.info("TTS 第%d句完成 耗时%.1fs 音频%.1fs (sr=%d)", idx + 1, t_tts, dur, sr)
                    inner_queue.put((wav_data, sr, last_sentence))
                except Exception as e:
                    logger.error("TTS 合成失败: %s", e)

            # 结束信号
            inner_queue.put(None)
            done_event.wait()

            if request_id:
                _trace_event(request_id, "tts_end")
                _trace_event(request_id, "play_end")
        except Exception as e:
            logger.error("TTS 播放失败: %s", e)
        finally:
            try:
                _pa_instance.terminate()
            except Exception:
                pass
            self.set_state(STATE_IDLE)
            self._set_ai_status("idle")

    def get_state(self) -> int:
        with self._lock:
            return self._state

    def set_state(self, s: int):
        with self._lock:
            self._state = s

    def _close_wakeword_stream(self):
        """关掉唤醒词检测流（IDLE→其他状态时调用）"""
        if self._wakeword_stream:
            try:
                self._wakeword_stream.close()
                logger.debug("唤醒词检测流已关闭")
            except Exception as e:
                logger.warning("关闭唤醒词检测流异常: %s", e)
            self._wakeword_stream = None

    def _get_debug_threshold(self) -> float:
        """获取调试阈值（低于主阈值但高于此值时记录调试信息）"""
        try:
            url = cfg.get_service_url("db_services", "/api/wakeword/debug-threshold")
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json().get("debug_threshold", 0.5)
        except Exception:
            pass
        return 0.5

    def _save_debug_audio(self, audio: np.ndarray, sr: int, score: float):
        """保存调试音频（接近阈值但未触发的唤醒候选）"""
        debug_dir = os.path.join(_WAKEWORD_DIR, "debug")
        os.makedirs(debug_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(debug_dir, f"{ts}_{score:.4f}.wav")
        try:
            with wave.open(filepath, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(audio.tobytes())
            logger.debug("调试音频已保存: %s (score=%.4f)", filepath, score)
        except Exception as e:
            logger.warning("保存调试音频失败: %s", e)

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

    def _run_loop(self):
        try:
            import pyaudio
            from livekit.wakeword import WakeWordModel
            from src.common.utils.tracer import trace_event as _trace_event, trace_content as _trace_content
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

            pa = pyaudio.PyAudio()
            buffer: list[np.ndarray] = []
            last_detection_time = 0.0
            debounce = 1.0
            check_counter = 0

            # 在循环外获取阈值
            threshold = self._get_threshold()
            frame_samples = self._get_frame_samples()

            while self._running:
                # ==================== IDLE ====================
                if self._state == STATE_IDLE:
                    # 1. 播放队列优先
                    if not self._play_queue.empty():
                        self._close_wakeword_stream()
                        self._state = STATE_PLAYING
                        continue

                    # 2. 确保流开着
                    buffer_frames = max(1, 32000 // frame_samples)

                    if self._wakeword_stream is None:
                        logger.info("开启唤醒词检测流")
                        self._wakeword_stream = pa.open(
                            format=pyaudio.paInt16,
                            channels=1,
                            rate=16000,
                            input=True,
                            frames_per_buffer=frame_samples,
                        )

                    # 3. 读帧
                    data = self._wakeword_stream.read(frame_samples, exception_on_overflow=False)
                    frame = np.frombuffer(data, dtype=np.int16)
                    buffer.append(frame)
                    while len(buffer) > buffer_frames:
                        buffer.pop(0)
                    if len(buffer) < buffer_frames:
                        continue

                    # 4. 唤醒检测
                    chunk = np.concatenate(buffer)
                    scores = model.predict(chunk)
                    best = max(scores.values()) if scores else 0.0

                    debug_threshold = self._get_debug_threshold()
                    if debug_threshold <= best < threshold:
                        logger.debug("唤醒词候选: score=%.4f (调试=%.2f, 主阈值=%.2f)", best, debug_threshold, threshold)
                        self._save_debug_audio(chunk, 16000, best)

                    now = time.time()
                    if best >= threshold and (now - last_detection_time) >= debounce:
                        last_detection_time = now
                        logger.info("检测到唤醒词: score=%.4f", best)

                        wakeword_id = self._save_wakeword_audio(chunk, 16000, best)
                        buffer.clear()
                        trace_request_id = f"voice_{uuid.uuid4().hex[:12]}"
                        _trace_event(trace_request_id, "wakeword", score=best)
                        self._close_wakeword_stream()
                        self._state = STATE_PLAYING
                        self.play_sync("我在呢")
                        self._state = STATE_RECORDING
                        continue

                # ==================== PLAYING ====================
                elif self._state == STATE_PLAYING:
                    logger.info("进入STATE_PLAYING")
                    text, request_id = self._play_queue.get()
                    self._close_wakeword_stream()
                    self.play_sync(text, request_id)
                    self._state = STATE_IDLE
                    continue

                # ==================== RECORDING ====================
                elif self._state == STATE_RECORDING:
                    logger.info("进入STATE_RECORDING")

                    # 开线程发 HTTP（ai_status + trace），不阻塞录音
                    def _recording_setup():
                        self._set_ai_status("listening")
                        _trace_event(trace_request_id, "wakeword", protocol="voice")
                    setup_thread = threading.Thread(target=_recording_setup, daemon=True)
                    setup_thread.start()

                    # 立即开始 VAD 录音（与 HTTP 并行）
                    try:
                        silence_ms = self._get_vad_silence()
                        wav_path = vad_record(timeout_sec=_VAD_TIMEOUT, silence_ms=silence_ms)
                    except Exception as e:
                        logger.error("VAD 录音失败: %s", e)
                        self._state = STATE_IDLE
                        self._update_wakeword_category(wakeword_id, "negative")
                        continue

                    # 等待 HTTP 完成
                    setup_thread.join(timeout=3)
                    _trace_event(trace_request_id, "record_end")
                    self._state = STATE_PROCESSING
                    continue

                # ==================== PROCESSING ====================
                elif self._state == STATE_PROCESSING:
                    logger.info("进入STATE_PROCESSING")
                    _trace_event(trace_request_id, "brain_receive", protocol="voice", user_id="u_temp_voice")
                    user_id = "u_temp_voice"
                    speaker = "未知用户"
                    audio_path = wav_path
                    text = ""

                    # 声纹识别
                    try:
                        user_id, speaker, audio_path = self._vp.detect(wav_path, wakeword_id)
                    except Exception as e:
                        logger.warning("声纹识别失败: %s", e)
                    _trace_event(trace_request_id, "voiceprint_end", metadata={"speaker": speaker, "user_id": user_id})
                    
                    # STT识别
                    try:
                        text = self._stt.transcribe(audio_path)
                        logger.info("STT 结果: %s", text[:100])
                    except Exception as e:
                        logger.warning("STT 失败: %s", e)
                    _trace_event(trace_request_id, "stt_end")

                    # 检测有没有有效的识别结果
                    if not text.strip():
                        logger.info("未检测到语音，跳过")
                        self._update_wakeword_category(wakeword_id, "negative")
                        self._wakeword_stream = pa.open(
                            format=pyaudio.paInt16, channels=1, rate=16000,
                            input=True, frames_per_buffer=self._get_frame_samples(),
                        )
                        self._state = STATE_IDLE
                        continue

                    # 记录识别结果
                    _trace_content(trace_request_id, text)
                    self._set_ai_status("thinking", speaker=speaker, message=text[:80])

                    url = cfg.get_service_url("brain_services", "/api/agent-request")
                    req_body = {
                        "protocol": "voice",
                        "request_id": trace_request_id,
                        "chat_type": "voice",
                        "user_id": user_id,
                        "content_type": "text",
                        "content": text,
                        "metadata": {"wakeword_id": wakeword_id, "speaker": speaker},
                    }
                    try:
                        requests.post(url, json=req_body, timeout=10)
                    except Exception as e:
                        logger.error("brain_services 调用失败: %s", e)

                    buffer.clear()
                    self._state = STATE_IDLE

            self._close_wakeword_stream()
            pa.terminate()

        except Exception as e:
            logger.error("唤醒词引擎异常: %s", e, exc_info=True)
