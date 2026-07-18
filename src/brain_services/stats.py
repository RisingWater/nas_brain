"""brain_services — 全局统计计数器"""
import time
import threading
from typing import Optional


class StatsCollector:
    """线程安全的统计计数器"""

    def __init__(self):
        self._lock = threading.Lock()
        self.start_time = time.time()
        self.total_requests = 0
        self.total_answers = 0          # 非 SKIP 回复数
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def record_request(self, answered: bool = False):
        with self._lock:
            self.total_requests += 1
            if answered:
                self.total_answers += 1

    def record_tokens(self, prompt: int, completion: int):
        with self._lock:
            self.prompt_tokens += prompt
            self.completion_tokens += completion

    def get_stats(self) -> dict:
        with self._lock:
            uptime = time.time() - self.start_time
            return {
                "uptime_seconds": int(uptime),
                "total_requests": self.total_requests,
                "total_answers": self.total_answers,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.prompt_tokens + self.completion_tokens,
            }


# 全局单例
stats = StatsCollector()
