# db_services/repositories/user_repository.py
import sqlite3
import uuid
import threading
from typing import Optional, Dict, List
from ..db_connection import db


class UserRepository:
    """用户 CRUD 操作（单例）"""
    
    _instance: Optional["UserRepository"] = None
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
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        return db.get_connection()
    
    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                user_type TEXT NOT NULL DEFAULT 'person',
                wechat_name TEXT,
                is_temp BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON users(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_wechat_name ON users(wechat_name)")
        conn.commit()
    
    def add_user(self, display_name: str, user_type: str = "person",
                 wechat_name: str = None, is_temp: bool = False) -> str:
        user_id = f"u_{uuid.uuid4().hex[:8]}" if not is_temp else f"u_temp_{uuid.uuid4().hex[:8]}"
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO users 
               (user_id, display_name, user_type, wechat_name, is_temp)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, display_name, user_type, wechat_name, 1 if is_temp else 0)
        )
        conn.commit()
        return user_id
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        conn = self._get_conn()
        cursor = conn.execute(
            """SELECT user_id, display_name, user_type, wechat_name, is_temp, created_at, is_active
               FROM users WHERE user_id = ? AND is_active = 1""",
            (user_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "user_id": row[0],
            "display_name": row[1],
            "user_type": row[2],
            "wechat_name": row[3],
            "is_temp": bool(row[4]),
            "created_at": row[5],
            "is_active": bool(row[6]),
        }
    
    def get_user_by_wechat(self, wechat_name: str) -> Optional[Dict]:
        conn = self._get_conn()
        cursor = conn.execute(
            """SELECT user_id, display_name, user_type, is_temp 
               FROM users WHERE wechat_name = ? AND is_active = 1""",
            (wechat_name,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "user_id": row[0],
            "display_name": row[1],
            "user_type": row[2],
            "is_temp": bool(row[3]),
        }
    
    def list_users(self, user_type: str = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        conn = self._get_conn()
        if user_type:
            cursor = conn.execute(
                """SELECT user_id, display_name, user_type, wechat_name, is_temp, created_at
                   FROM users WHERE is_active = 1 AND user_type = ? 
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (user_type, limit, offset)
            )
        else:
            cursor = conn.execute(
                """SELECT user_id, display_name, user_type, wechat_name, is_temp, created_at
                   FROM users WHERE is_active = 1 
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (limit, offset)
            )
        return [
            {
                "user_id": row[0],
                "display_name": row[1],
                "user_type": row[2],
                "wechat_name": row[3],
                "is_temp": bool(row[4]),
                "created_at": row[5],
            }
            for row in cursor.fetchall()
        ]
    
    def update_user(self, user_id: str, display_name: str = None,
                    wechat_name: str = None, is_temp: bool = None) -> bool:
        fields = []
        values = []
        if display_name is not None:
            fields.append("display_name = ?")
            values.append(display_name)
        if wechat_name is not None:
            fields.append("wechat_name = ?")
            values.append(wechat_name)
        if is_temp is not None:
            fields.append("is_temp = ?")
            values.append(1 if is_temp else 0)
        if not fields:
            return True
        values.append(user_id)
        conn = self._get_conn()
        conn.execute(
            f"UPDATE users SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND is_active = 1",
            values
        )
        conn.commit()
        return conn.total_changes > 0
    
    def delete_user(self, user_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT is_temp FROM users WHERE user_id = ? AND is_active = 1",
            (user_id,)
        )
        row = cursor.fetchone()
        if not row:
            return False
        is_temp = bool(row[0])
        if is_temp:
            conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        else:
            conn.execute(
                "UPDATE users SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (user_id,)
            )
        conn.commit()
        return conn.total_changes > 0


# 全局单例
user_repo = UserRepository.instance()