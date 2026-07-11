"""db_services — 中期记忆（chat_summaries）CRUD"""
from fastapi import APIRouter, HTTPException
from ..db_connection import db
from ..schema.chat_schema import ChatSummaryCreate, ChatSummaryResponse

router = APIRouter()


def _init_table():
    conn = db.get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_summaries (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT NOT NULL,
            summary         TEXT NOT NULL,
            last_msg_id     INTEGER NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_summaries_user ON chat_summaries(user_id)")
    conn.commit()


_init_table()


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "summary": row["summary"],
        "last_msg_id": row["last_msg_id"],
        "created_at": row["created_at"],
    }


@router.post("", status_code=201)
def add_summary(req: ChatSummaryCreate):
    """写入一条中期记忆总结"""
    conn = db.get_connection()
    cursor = conn.execute(
        "INSERT INTO chat_summaries (user_id, summary, last_msg_id) VALUES (?, ?, ?)",
        (req.user_id, req.summary, req.last_msg_id),
    )
    conn.commit()
    return {"success": True, "id": cursor.lastrowid}


@router.get("/{user_id}/latest", response_model=ChatSummaryResponse)
def get_latest_summary(user_id: str):
    """取用户最新的中期记忆总结"""
    conn = db.get_connection()
    row = conn.execute(
        "SELECT * FROM chat_summaries WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, f"user {user_id} 暂无中期记忆")
    return ChatSummaryResponse(**_row_to_dict(row))


@router.get("/{user_id}/list")
def list_summaries(user_id: str, limit: int = 20):
    """取用户的所有中期记忆（按时间倒序）"""
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT * FROM chat_summaries WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return {"total": len(rows), "items": [_row_to_dict(r) for r in rows]}


@router.get("/{user_id}/max-msg-id")
def get_summary_max_msg_id(user_id: str):
    """取用户已总结到的最大消息 ID"""
    conn = db.get_connection()
    row = conn.execute(
        "SELECT MAX(last_msg_id) as max_id FROM chat_summaries WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return {"user_id": user_id, "max_id": row["max_id"] or 0}


@router.delete("/{user_id}")
def clear_summaries(user_id: str, keep_latest: bool = False):
    """清理用户的总结记录"""
    conn = db.get_connection()
    if keep_latest:
        # 只保留最新一条
        latest = conn.execute(
            "SELECT id FROM chat_summaries WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if latest:
            conn.execute("DELETE FROM chat_summaries WHERE user_id = ? AND id != ?",
                         (user_id, latest["id"]))
    else:
        conn.execute("DELETE FROM chat_summaries WHERE user_id = ?", (user_id,))
    conn.commit()
    return {"success": True, "user_id": user_id}
