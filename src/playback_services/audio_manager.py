"""音频播放管理器 — 独立播放线程 + 队列，统一管理 pyaudio 输出"""
import logging
import queue
import threading
import pyaudio

logger = logging.getLogger("playback_services")

# WAV 的 PCM 16-bit 格式常量
_PA_FORMAT_WAV = pyaudio.paInt16


class AudioManager:
    """音频播放管理器

    内部维护一个后台播放线程 + 队列，所有音频统一排队播放。
    支持 async（丢队列就返回）和 sync（阻塞到播完）。
    """

    def __init__(self, sample_rate: int = 24000, device: int | None = None):
        self.sample_rate = sample_rate
        self.device = device
        self._queue: queue.Queue[bytes | None] = queue.Queue()
        self._done_events: dict[int, threading.Event] = {}
        self._id_counter = 0
        self._lock = threading.Lock()
        self._running = True

        self._thread = threading.Thread(target=self._play_loop, daemon=True)
        self._thread.start()
        logger.info("音频播放管理器已启动 (sample_rate=%d)", sample_rate)

    def play_async(self, wav_bytes: bytes, sample_rate: int = 0):
        """异步播放 — 入队立即返回"""
        sr = sample_rate or self.sample_rate
        self._queue.put((wav_bytes, sr))

    def play_sync(self, wav_bytes: bytes, sample_rate: int = 0):
        """同步播放 — 入队并阻塞直到播完"""
        sr = sample_rate or self.sample_rate
        with self._lock:
            self._id_counter += 1
            chunk_id = self._id_counter
            event = threading.Event()
            self._done_events[chunk_id] = event
        self._queue.put((chunk_id, wav_bytes, sr))
        event.wait()

    def stop(self):
        self._running = False
        self._queue.put(None)

    def _play_loop(self):
        pa = pyaudio.PyAudio()
        try:
            while self._running:
                item = self._queue.get()
                if item is None:
                    break

                # 解析队列项
                if len(item) == 3:  # sync: (chunk_id, data, sr)
                    chunk_id, data, sr = item
                elif len(item) == 2:  # async: (data, sr)
                    data, sr = item
                    chunk_id = None
                else:
                    continue

                try:
                    stream = pa.open(
                        format=_PA_FORMAT_WAV,
                        channels=1,
                        rate=sr,
                        output=True,
                        output_device_index=self.device,
                    )
                    stream.write(data)
                    stream.stop_stream()
                    stream.close()
                except Exception as e:
                    logger.error("播放失败: %s", e)

                if chunk_id is not None:
                    with self._lock:
                        if chunk_id in self._done_events:
                            self._done_events.pop(chunk_id).set()
        finally:
            pa.terminate()
            logger.info("音频播放线程已退出")


# 全局单例
_manager: AudioManager | None = None
_manager_lock = threading.Lock()


def get_audio_manager() -> AudioManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = AudioManager()
    return _manager
