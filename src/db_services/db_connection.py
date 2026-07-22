# db_services/db_connection.py
import sqlite3
import threading
from typing import Optional
from src.common.utils import cfg

class DBConnection:
    """SQLite 数据库连接单例 — 每个线程独立连接，WAL 模式"""

    _instance: Optional["DBConnection"] = None
    _lock = threading.Lock()
    _local = threading.local()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    @classmethod
    def instance(cls):
        return cls()

    def _init(self):
        self.db_path = cfg.DB_PATH

    def _new_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=10.0,
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        # 宽松 UTF-8 解码，避免已有损坏数据导致崩溃
        conn.text_factory = lambda x: x.decode("utf-8", "replace")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def get_connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._new_conn()
            self._local.conn = conn
        return conn

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None


# 全局单例
db = DBConnection.instance()