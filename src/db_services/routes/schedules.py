"""db_services — 定时任务 schedules 表 CRUD"""
import sqlite3
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ..db_connection import db
from ..schema.schedule_schema import (
    AddScheduleRequest, UpdateScheduleRequest, ScheduleResponse, ListSchedulesResponse,
)

router = APIRouter()


def _init_table():
    conn = db.get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            content     TEXT NOT NULL,
            rtype       TEXT NOT NULL DEFAULT 'once',
            rdatetime   TEXT,
            lunar       INTEGER DEFAULT 0,
            strategy    TEXT NOT NULL DEFAULT 'direct',
            prompt      TEXT,
            notify_type TEXT NOT NULL DEFAULT 'wechat',
            done        INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


# 启动时建表
_init_table()


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "content": row["content"],
        "rtype": row["rtype"],
        "rdatetime": row["rdatetime"],
        "lunar": bool(row["lunar"]),
        "strategy": row["strategy"],
        "prompt": row["prompt"],
        "notify_type": row["notify_type"],
        "done": bool(row["done"]),
        "created_at": row["created_at"],
    }


@router.post("", status_code=201)
def add_schedule(req: AddScheduleRequest):
    conn = db.get_connection()
    cursor = conn.execute(
        """INSERT INTO schedules (user_id, content, rtype, rdatetime, lunar, strategy, prompt, notify_type)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (req.user_id, req.content, req.rtype, req.rdatetime or None,
         1 if req.lunar else 0, req.strategy, req.prompt, req.notify_type),
    )
    conn.commit()
    return {"success": True, "id": cursor.lastrowid}


@router.get("", response_model=ListSchedulesResponse)
def list_schedules(
    done: Optional[bool] = Query(None),
    rtype: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    conn = db.get_connection()
    conditions = []
    params = []
    if done is not None:
        conditions.append("done = ?")
        params.append(1 if done else 0)
    if rtype:
        conditions.append("rtype = ?")
        params.append(rtype)
    if keyword:
        conditions.append("content LIKE ?")
        params.append(f"%{keyword}%")
    where = " AND ".join(conditions) if conditions else "1=1"

    # total
    total_row = conn.execute(f"SELECT COUNT(*) FROM schedules WHERE {where}", params).fetchone()
    total = total_row[0]

    # page
    cursor = conn.execute(
        f"SELECT * FROM schedules WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    rows = [_row_to_dict(r) for r in cursor.fetchall()]
    return ListSchedulesResponse(total=total, schedules=rows)


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(schedule_id: int):
    conn = db.get_connection()
    cursor = conn.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(404, f"schedule {schedule_id} 不存在")
    return ScheduleResponse(**_row_to_dict(row))


@router.put("/{schedule_id}")
def update_schedule(schedule_id: int, req: UpdateScheduleRequest):
    conn = db.get_connection()
    existing = conn.execute("SELECT id FROM schedules WHERE id = ?", (schedule_id,)).fetchone()
    if not existing:
        raise HTTPException(404, f"schedule {schedule_id} 不存在")

    fields = []
    values = []
    for key, col in [
        ("content", "content"), ("rtype", "rtype"), ("rdatetime", "rdatetime"),
        ("strategy", "strategy"), ("prompt", "prompt"), ("notify_type", "notify_type"),
    ]:
        val = getattr(req, key, None)
        if val is not None:
            fields.append(f"{col} = ?")
            values.append(val)
    if req.lunar is not None:
        fields.append("lunar = ?")
        values.append(1 if req.lunar else 0)
    if req.done is not None:
        fields.append("done = ?")
        values.append(1 if req.done else 0)

    if not fields:
        return {"success": True}
    values.append(schedule_id)
    conn.execute(
        f"UPDATE schedules SET {', '.join(fields)} WHERE id = ?", values,
    )
    conn.commit()
    return {"success": True}


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: int):
    conn = db.get_connection()
    existing = conn.execute("SELECT id FROM schedules WHERE id = ?", (schedule_id,)).fetchone()
    if not existing:
        raise HTTPException(404, f"schedule {schedule_id} 不存在")
    conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
    conn.commit()
    return {"success": True, "id": schedule_id}


@router.post("/{schedule_id}/mark-done")
def mark_done(schedule_id: int):
    conn = db.get_connection()
    existing = conn.execute("SELECT id FROM schedules WHERE id = ?", (schedule_id,)).fetchone()
    if not existing:
        raise HTTPException(404, f"schedule {schedule_id} 不存在")
    conn.execute("UPDATE schedules SET done = 1 WHERE id = ?", (schedule_id,))
    conn.commit()
    return {"success": True}


@router.get("/stats")
def schedule_stats():
    conn = db.get_connection()
    total = conn.execute("SELECT COUNT(*) FROM schedules").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM schedules WHERE done = 0").fetchone()[0]
    done = conn.execute("SELECT COUNT(*) FROM schedules WHERE done = 1").fetchone()[0]
    return {
        "total": total,
        "pending": pending,
        "done": done,
    }
