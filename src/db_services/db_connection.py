# src/common/db/db_connection.py
import sqlite3
import threading
from typing import Optional
from common.utils import cfg

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
        self.db_path = getattr(cfg, 'DB_PATH', 'data/users.db')
        self._conn: Optional[sqlite3.Connection] = None
        self._conn_lock = threading.Lock()
    
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接（单例）"""
        if self._conn is None:
            with self._conn_lock:
                if self._conn is None:
                    self._conn = sqlite3.connect(
                        self.db_path,
                        check_same_thread=False,      # 多线程共享
                        timeout=10.0,                 # 等待锁超时 10 秒
                        isolation_level=None          # 自动提交模式
                    )
                    self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def execute(self, sql: str, params=()):
        """快捷执行"""
        conn = self.get_connection()
        return conn.execute(sql, params)
    
    def executemany(self, sql: str, params_list):
        """批量执行"""
        conn = self.get_connection()
        return conn.executemany(sql, params_list)
    
    def __enter__(self):
        return self.get_connection()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass  # 不关闭连接，留给单例管理


# 全局单例
db = DBConnection.instance()