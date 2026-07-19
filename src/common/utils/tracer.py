"""链路追踪工具 — 各微服务通用打点"""
import os
import logging
import threading
from typing import Optional

logger = logging.getLogger("tracer")

# 缓存 db_services URL
_TRACER_URL: Optional[str] = None
_lock = threading.Lock()


def _get_url() -> str:
    global _TRACER_URL
    if _TRACER_URL is None:
        with _lock:
            if _TRACER_URL is None:
                port = os.getenv("DB_SERVICE_PORT", "9021")
                _TRACER_URL = f"http://127.0.0.1:{port}/api/request-traces"
    return _TRACER_URL


def trace_event(request_id: str, stage: str, metadata: dict | None = None,
                protocol: str = "", user_id: str = ""):
    """记录一个追踪事件（异步、静默失败）"""
    try:
        import requests as _req
        _req.post(
            f"{_get_url()}/event",
            json={
                "request_id": request_id,
                "stage": stage,
                "metadata": metadata or {},
                "protocol": protocol,
                "user_id": user_id,
            },
            timeout=3,
        )
    except Exception:
        pass  # 静默失败，不影响主流程


def trace_content(request_id: str, content: str):
    """更新请求内容"""
    try:
        import requests as _req
        _req.put(
            f"{_get_url()}/{request_id}/content",
            json={"content": content},
            timeout=3,
        )
    except Exception:
        pass


def trace_reply(request_id: str, reply: str = "", skip: bool = False):
    """更新回复信息"""
    try:
        import requests as _req
        _req.put(
            f"{_get_url()}/{request_id}/reply",
            json={"reply": reply, "skip": skip},
            timeout=3,
        )
    except Exception:
        pass
