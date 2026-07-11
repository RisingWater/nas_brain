"""db_services — 聊天记录 CRUD + 搜索"""
import json
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Any, Dict
from ..db_connection import db
from ..schema.chat_schema import (
    ChatMessageCreate, BatchChatMessageCreate, ChatMessageResponse,
    ChatHistoryResponse,
)

router = APIRouter()


def _init_table():
    conn = db.get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT NOT NULL,
            role            TEXT NOT NULL CHECK(role IN ('user','assistant','tool','processor')),
            content         TEXT,
            tool_calls      TEXT,
            tool_name       TEXT,
            tool_result     TEXT,
            processor_name  TEXT,
            protocol        TEXT DEFAULT 'wechat',
            chat_type       TEXT DEFAULT 'private',
            metadata        TEXT DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_msg_user_time ON chat_messages(user_id, created_at)")
    conn.commit()


_init_table()


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "role": row["role"],
        "content": row["content"],
        "tool_calls": json.loads(row["tool_calls"]) if row["tool_calls"] else None,
        "tool_name": row["tool_name"],
        "tool_result": json.loads(row["tool_result"]) if row["tool_result"] else None,
        "processor_name": row["processor_name"],
        "protocol": row["protocol"],
        "chat_type": row["chat_type"],
        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
        "created_at": row["created_at"],
    }


@router.post("", status_code=201)
def add_chat_message(req: ChatMessageCreate):
    """写入单条聊天记录"""
    conn = db.get_connection()
    cursor = conn.execute(
        """INSERT INTO chat_messages (user_id, role, content, tool_calls, tool_name, tool_result,
           processor_name, protocol, chat_type, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (req.user_id, req.role, req.content,
         json.dumps(req.tool_calls, ensure_ascii=False) if req.tool_calls else None,
         req.tool_name,
         json.dumps(req.tool_result, ensure_ascii=False) if req.tool_result else None,
         req.processor_name, req.protocol, req.chat_type,
         json.dumps(req.metadata, ensure_ascii=False) if req.metadata else "{}"),
    )
    conn.commit()
    return {"success": True, "id": cursor.lastrowid}


@router.post("/batch", status_code=201)
def add_chat_messages_batch(req: BatchChatMessageCreate):
    """批量写入聊天记录"""
    conn = db.get_connection()
    ids = []
    for msg in req.messages:
        cursor = conn.execute(
            """INSERT INTO chat_messages (user_id, role, content, tool_calls, tool_name, tool_result,
               processor_name, protocol, chat_type, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (msg.user_id, msg.role, msg.content,
             json.dumps(msg.tool_calls, ensure_ascii=False) if msg.tool_calls else None,
             msg.tool_name,
             json.dumps(msg.tool_result, ensure_ascii=False) if msg.tool_result else None,
             msg.processor_name, msg.protocol, msg.chat_type,
             json.dumps(msg.metadata, ensure_ascii=False) if msg.metadata else "{}"),
        )
        ids.append(cursor.lastrowid)
    conn.commit()
    return {"success": True, "ids": ids}


@router.get("/{user_id}", response_model=ChatHistoryResponse)
def get_chat_history(
    user_id: str,
    limit: int = Query(50, ge=1, le=500),
    before_id: Optional[int] = Query(None, ge=0),
    since_id: Optional[int] = Query(None, ge=0),
    since_time: Optional[str] = Query(None),
):
    """查询聊天历史，支持分页和时间范围"""
    conn = db.get_connection()
    conditions = ["user_id = ?"]
    params = [user_id]

    if before_id:
        conditions.append("id < ?")
        params.append(before_id)
    if since_id:
        conditions.append("id > ?")
        params.append(since_id)
    if since_time:
        conditions.append("created_at >= ?")
        params.append(since_time)

    where = " AND ".join(conditions)
    total = conn.execute(f"SELECT COUNT(*) FROM chat_messages WHERE {where}", params).fetchone()[0]

    cursor = conn.execute(
        f"SELECT * FROM chat_messages WHERE {where} ORDER BY id DESC LIMIT ?",
        (*params, limit),
    )
    rows = [_row_to_dict(r) for r in cursor.fetchall()]
    rows.reverse()  # 按时间正序返回
    return ChatHistoryResponse(total=total, messages=rows)


@router.get("/search")
def search_chat_messages(
    keyword: str = Query(..., min_length=1),
    user_id: Optional[str] = Query(None),
    hours_back: int = Query(72, ge=1, le=720),
    limit: int = Query(10, ge=1, le=50),
):
    """全文搜索聊天记录（给 SearchChatHistoryTool 用）"""
    conn = db.get_connection()
    conditions = ["content LIKE ?"]
    params = [f"%{keyword}%"]

    if user_id:
        conditions.append("user_id = ?")
        params.append(user_id)

    conditions.append("created_at >= datetime('now', ? || ' hours')")
    params.append(f"-{hours_back}")

    # 只搜 user/assistant/processor 角色，不搜 tool 结果
    conditions.append("role IN ('user','assistant','processor')")

    where = " AND ".join(conditions)
    cursor = conn.execute(
        f"SELECT * FROM chat_messages WHERE {where} ORDER BY created_at DESC LIMIT ?",
        (*params, limit),
    )
    rows = [_row_to_dict(r) for r in cursor.fetchall()]
    return {"total": len(rows), "messages": rows}


@router.get("/{user_id}/max-id")
def get_max_message_id(user_id: str):
    """查用户最大消息 ID（供总结器判断是否有新内容）"""
    conn = db.get_connection()
    row = conn.execute(
        "SELECT MAX(id) as max_id FROM chat_messages WHERE user_id = ?", (user_id,)
    ).fetchone()
    return {"user_id": user_id, "max_id": row["max_id"] or 0}


@router.delete("/single/{msg_id}")
def delete_message_by_id(msg_id: int):
    """按 ID 删除单条消息"""
    conn = db.get_connection()
    conn.execute("DELETE FROM chat_messages WHERE id = ?", (msg_id,))
    conn.commit()
    return {"success": True, "deleted_id": msg_id}


@router.delete("/{user_id}/last")
def delete_last_messages(user_id: str, count: int = Query(1, ge=1, le=20)):
    """删除用户最新的 N 条消息"""
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT id FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, count),
    ).fetchall()
    ids = [r["id"] for r in rows]
    if ids:
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"DELETE FROM chat_messages WHERE user_id = ? AND id IN ({placeholders})",
            (user_id, *ids),
        )
        conn.commit()
        return {"success": True, "user_id": user_id, "deleted_ids": ids}
    return {"success": True, "user_id": user_id, "deleted_ids": []}


@router.delete("/{user_id}")
def delete_chat_messages(user_id: str, before_id: Optional[int] = Query(None)):
    """清理旧聊天记录"""
    conn = db.get_connection()
    if before_id:
        conn.execute("DELETE FROM chat_messages WHERE user_id = ? AND id <= ?", (user_id, before_id))
    else:
        conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
    conn.commit()
    return {"success": True, "user_id": user_id}
