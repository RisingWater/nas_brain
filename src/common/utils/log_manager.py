"""日志管理 — LogManager 单例：磁盘持久化（20MB）+ 内存缓冲，供 Web UI 查看和导出"""
import logging
import logging.handlers
import os
import sys
import threading
import time
from src.common.utils import cfg
from collections import deque
from typing import Optional

_LOG_SERVER_NAME = os.getenv("LOG_SERVER_NAME", "test")
_LOG_FILE = os.path.join(cfg.LOG_DIR, f"{_LOG_SERVER_NAME}.log")

def _format_time(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) + f".{int(ts * 1000) % 1000:03d}"

def _ensure_log_dir():
    os.makedirs(cfg.LOG_DIR, exist_ok=True)


class _MemoryHandler(logging.Handler):
    """将日志记录写入 LogManager 的内存环形缓冲区"""

    def __init__(self, mgr: "LogManager"):
        super().__init__()
        self._mgr = mgr

    def emit(self, record: logging.LogRecord):
        try:
            self._mgr._append_record(record, self.format(record))
        except Exception:
            self.handleError(record)


class LogManager:
    """日志管理单例"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
            cls._instance.setup()
        return cls._instance

    @classmethod
    def instance(cls):
        return cls()

    def _init(self):
        self._buffer: deque = deque(maxlen=cfg.LOG_MAX_ENTRYS)
        self._lock = threading.Lock()
        self._counter = 0

    # ---- 初始化 ----
    def setup(self):
        """安装内存 + 磁盘日志处理器到根 logger，并接管 sys.excepthook"""
        # 让根 logger 放过所有级别（由 handler 自己控制过滤）
        logging.root.setLevel(logging.DEBUG)

        # 抑制第三方库的 DEBUG 日志，只保留 WARNING 以上
        for lib in ("urllib3", "requests", "httpcore", "httpx"):
            logging.getLogger(lib).setLevel(logging.WARNING)

        # 磁盘持久化
        _ensure_log_dir()
        file_handler = logging.handlers.RotatingFileHandler(
            _LOG_FILE, maxBytes=cfg.LOG_SIZE, backupCount=cfg.LOG_BACKUPS,
            encoding="utf-8", delay=False,
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)-8s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logging.root.addHandler(file_handler)

        # 内存缓冲
        mem_handler = _MemoryHandler(self)
        mem_handler.setLevel(logging.DEBUG)
        mem_handler.setFormatter(logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)-8s %(name)s %(message)s",
            datefmt="%H:%M:%S",
        ))
        logging.root.addHandler(mem_handler)

        # ===== 接管 Uvicorn 日志 =====
        for name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
            uvicorn_logger = logging.getLogger(name)
            uvicorn_logger.setLevel(logging.DEBUG)
            uvicorn_logger.addHandler(file_handler)
            uvicorn_logger.addHandler(mem_handler)
            uvicorn_logger.propagate = False

        # ===== 控制台输出（可选，通过环境变量控制） =====
        if os.getenv("LOG_CONSOLE", "true").lower() == "true":
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)-8s %(name)s %(message)s",
                datefmt="%H:%M:%S",
            ))
            logging.root.addHandler(console_handler)
            # Uvicorn 也加控制台
            for name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
                uvicorn_logger = logging.getLogger(name)
                uvicorn_logger.addHandler(console_handler)

        # 捕获未处理的异常
        _orig_excepthook = sys.excepthook
        def _log_excepthook(exc_type, exc_value, exc_tb):
            import traceback
            tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            logging.getLogger("unhandled").error("Unhandled exception:\n%s", tb_text.rstrip())
            _orig_excepthook(exc_type, exc_value, exc_tb)
        sys.excepthook = _log_excepthook

        if hasattr(threading, "excepthook"):
            _orig_threadhook = threading.excepthook
            def _log_threadhook(args):
                import traceback
                tb_text = "".join(traceback.format_exception(
                    args.exc_type, args.exc_value, args.exc_traceback))
                logging.getLogger("unhandled").error("Thread exception:\n%s", tb_text.rstrip())
                if _orig_threadhook:
                    _orig_threadhook(args)
            threading.excepthook = _log_threadhook

        # 启动日志
        logging.info(f"📝 日志初始化完成: {_LOG_FILE}")
        logging.info(f"📝 服务名: {_LOG_SERVER_NAME}")

    # ---- 内部 ----

    def _append_record(self, record: logging.LogRecord, msg: str):
        with self._lock:
            self._counter += 1
            self._buffer.append({
                "id": self._counter,
                "time": _format_time(record.created),
                "level": record.levelname,
                "name": record.name,
                "message": msg,
            })

    # ---- 查询 ----

    def get_logs(
        self, level: Optional[str] = None, search: Optional[str] = None,
        limit: int = 200, offset: int = 0,
    ) -> dict:
        with self._lock:
            entries = list(self._buffer)
            
        if level:
            level = level.upper()
            entries = [e for e in entries if e["level"] == level]
        if search:
            search_lower = search.lower()
            entries = [e for e in entries if search_lower in e["message"].lower()]

        total = len(entries)
        entries.reverse()
        page = entries[offset:offset + limit]
        return {"total": total, "logs": page}

    def export_text(self) -> str:
        files = [_LOG_FILE]
        for i in range(1, cfg.LOG_BACKUPS + 1):
            f = f"{_LOG_FILE}.{i}"
            if os.path.isfile(f):
                files.append(f)
        files.sort(key=lambda f: os.path.getmtime(f))
        lines = []
        for path in files:
            try:
                with open(path, encoding="utf-8") as fh:
                    lines.append(fh.read().rstrip())
            except Exception:
                pass
        return "\n".join(lines)

    def clear(self):
        with self._lock:
            self._buffer.clear()
            self._counter = 0
        for path in [_LOG_FILE] + [f"{_LOG_FILE}.{i}" for i in range(1, cfg.LOG_BACKUPS + 1)]:
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except Exception:
                pass


# 全局单例
log_mgr = LogManager()
