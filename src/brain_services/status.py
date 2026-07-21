"""brain_services — AI 状态管理器

状态定义:
  idle      空闲，等待输入
  listening 正在聆听（语音场景：唤醒→VAD录音中）
  thinking  LLM 处理中
  operating 工具调用中
  speaking  回复输出中（TTS播放 / 发送微信等）

流转:
  语音:   idle → listening → thinking → operating → speaking → idle
  Web/微信: idle → thinking → operating → speaking → idle
"""
import os
import time
import threading
from typing import Optional


# 可选状态列表
STATES = ("idle", "listening", "thinking", "operating", "speaking")
STATE_LABELS = {
    "idle": "空闲中",
    "listening": "正在聆听...",
    "thinking": "思考中...",
    "operating": "操作中...",
    "speaking": "说话中...",
}


class AIStatus:
    """线程安全的状态管理器"""

    def __init__(self):
        self._lock = threading.Lock()
        self._state: str = "idle"
        self._changed_at: float = time.time()
        self._speaker: str = ""
        self._message: str = ""
        self._extra: dict = {}

    def set(self, state: str, speaker: str = "", message: str = "", **extra):
        """设置状态，附带可选的说话人信息、上下文文字和额外数据"""
        assert state in STATES, f"无效状态: {state}"
        with self._lock:
            self._state = state
            self._changed_at = time.time()
            if speaker:
                self._speaker = speaker
            self._message = message  # 每次 set 更新上下文文字（传空字符串清空）
            if extra:
                self._extra.update(extra)
        # fire-and-forget 通知 web_services，不阻塞调用方
        threading.Thread(target=self._notify_web, daemon=True).start()

    def _notify_web(self):
        """异步通知 web_services 状态变更"""
        try:
            import requests as _req
            port = os.getenv("WEB_SERVICE_PORT", "9020")
            url = f"http://127.0.0.1:{port}/api/admin/ai-status/notify"
            _req.post(url, json=self.get(), timeout=2)
        except Exception:
            pass  # 静默失败，不影响主流程

    def get(self) -> dict:
        with self._lock:
            # 懒加载 uptime，避免循环导入
            uptime = 0
            try:
                from .stats import stats
                uptime = stats.get_stats().get("uptime_seconds", 0)
            except Exception:
                pass
            extra = dict(self._extra)
            extra["uptime_seconds"] = uptime
            return {
                "state": self._state,
                "label": STATE_LABELS.get(self._state, self._state),
                "changed_at": self._changed_at,
                "duration": round(time.time() - self._changed_at, 1),
                "speaker": self._speaker,
                "message": self._message,
                "extra": extra,
            }


# 全局单例
ai_status = AIStatus()
