# db_services/db_connection.py
import sqlite3
import threading
from typing import Optional
from src.common.utils import cfg

class DBConnection:
    """SQLite 数据库连接单例"""
    
    _instance: Optional["DBConnection"] = None
    _lock = threading.Lock()
    
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
        self._conn: Optional[sqlite3.Connection] = None
        self._conn_lock = threading.Lock()
    
    def get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            with self._conn_lock:
                if self._conn is None:
                    self._conn = sqlite3.connect(
                        self.db_path,
                        check_same_thread=False,
                        timeout=10.0,
                        isolation_level=None
                    )
                    self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


# 全局单例
db = DBConnection.instance()