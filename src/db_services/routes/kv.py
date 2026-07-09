"""db_services — 通用 KV 存储（键值对持久化，供 detector 等模块记录状态）"""
from fastapi import APIRouter, HTTPException, Query
from ..db_connection import db

router = APIRouter()


def _init_table():
    conn = db.get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kv_store (
            key         TEXT PRIMARY KEY,
            value       TEXT,
            namespace   TEXT DEFAULT '',
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_kv_namespace ON kv_store(namespace)")
    conn.commit()


_init_table()


@router.get("/{key}")
def get_kv(key: str):
    """获取键值"""
    conn = db.get_connection()
    row = conn.execute("SELECT value FROM kv_store WHERE key = ?", (key,)).fetchone()
    if not row:
        raise HTTPException(404, f"key '{key}' 不存在")
    return {"key": key, "value": row[0]}


@router.put("/{key}")
def set_kv(key: str, body: dict):
    """设置键值（upsert）"""
    value = body.get("value", "")
    namespace = body.get("namespace", "")
    conn = db.get_connection()
    conn.execute(
        """INSERT INTO kv_store (key, value, namespace, updated_at)
           VALUES (?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                          namespace = excluded.namespace,
                                          updated_at = CURRENT_TIMESTAMP""",
        (key, value, namespace),
    )
    conn.commit()
    return {"success": True, "key": key}


@router.delete("/{key}")
def delete_kv(key: str):
    """删除键值"""
    conn = db.get_connection()
    conn.execute("DELETE FROM kv_store WHERE key = ?", (key,))
    conn.commit()
    return {"success": True, "key": key}


@router.get("")
def list_kv(namespace: str = Query(""), prefix: str = Query("")):
    """按 namespace 或 key 前缀查询"""
    conn = db.get_connection()
    if namespace:
        rows = conn.execute(
            "SELECT key, value, namespace, updated_at FROM kv_store WHERE namespace = ? ORDER BY key",
            (namespace,),
        ).fetchall()
    elif prefix:
        rows = conn.execute(
            "SELECT key, value, namespace, updated_at FROM kv_store WHERE key LIKE ? ORDER BY key",
            (f"{prefix}%",),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT key, value, namespace, updated_at FROM kv_store ORDER BY key"
        ).fetchall()
    return {
        "total": len(rows),
        "items": [{"key": r[0], "value": r[1], "namespace": r[2], "updated_at": r[3]} for r in rows],
    }
