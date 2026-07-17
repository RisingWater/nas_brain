"""db_services — 用户策略配置 CRUD"""
import json
from fastapi import APIRouter, HTTPException
from ..db_connection import db
from ..schema.config_schema import (
    UserConfigUpdateRequest, UserConfigResponse,
)

router = APIRouter()

_DEFAULT = {
    "strategy": "ignore",
    "system_prompt": "",
    "allowed_tools": None,
    "allowed_processors": None,
    "short_term_window": 30,
    "group_at_only": True,
}


def _init_table():
    conn = db.get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_configs (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id            TEXT UNIQUE NOT NULL,
            strategy           TEXT NOT NULL DEFAULT 'ignore',
            system_prompt      TEXT DEFAULT '',
            allowed_tools      TEXT,
            allowed_processors TEXT,
            short_term_window  INTEGER DEFAULT 30,
            group_at_only      INTEGER DEFAULT 1,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 兼容：添加 allowed_processors 列（旧表没有）
    try:
        conn.execute("ALTER TABLE user_configs ADD COLUMN allowed_processors TEXT")
        conn.commit()
    except Exception:
        pass
    conn.commit()


_init_table()


def _row_to_dict(row) -> dict:
    return {
        "user_id": row["user_id"] or "",
        "strategy": row["strategy"] or "ignore",
        "system_prompt": row["system_prompt"] or "",
        "allowed_tools": json.loads(row["allowed_tools"]) if row["allowed_tools"] else None,
        "allowed_processors": json.loads(row["allowed_processors"]) if row["allowed_processors"] else None,
        "short_term_window": row["short_term_window"] or 30,
        "group_at_only": bool(row["group_at_only"]) if row["group_at_only"] is not None else True,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@router.get("")
def list_user_configs(limit: int = 200, offset: int = 0):
    """列出所有用户配置"""
    conn = db.get_connection()
    total = conn.execute("SELECT COUNT(*) FROM user_configs").fetchone()[0]
    rows = conn.execute(
        "SELECT * FROM user_configs ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return {"total": total, "items": [_row_to_dict(r) for r in rows]}


@router.get("/{user_id}", response_model=UserConfigResponse)
def get_user_config(user_id: str):
    """获取用户配置（不存在则返回默认值）"""
    conn = db.get_connection()
    row = conn.execute("SELECT * FROM user_configs WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return UserConfigResponse(user_id=user_id, **_DEFAULT)
    return UserConfigResponse(**_row_to_dict(row))


@router.put("/{user_id}")
def update_user_config(user_id: str, req: UserConfigUpdateRequest):
    """更新/创建用户配置"""
    conn = db.get_connection()
    existing = conn.execute("SELECT id FROM user_configs WHERE user_id = ?", (user_id,)).fetchone()

    fields = ["updated_at = CURRENT_TIMESTAMP"]
    values = []
    if req.strategy is not None:
        fields.append("strategy = ?")
        values.append(req.strategy)
    if req.system_prompt is not None:
        fields.append("system_prompt = ?")
        values.append(req.system_prompt)
    if req.allowed_tools is not None:
        fields.append("allowed_tools = ?")
        values.append(json.dumps(req.allowed_tools, ensure_ascii=False))
    if req.allowed_processors is not None:
        fields.append("allowed_processors = ?")
        values.append(json.dumps(req.allowed_processors, ensure_ascii=False))
    if req.short_term_window is not None:
        fields.append("short_term_window = ?")
        values.append(req.short_term_window)
    if req.group_at_only is not None:
        fields.append("group_at_only = ?")
        values.append(1 if req.group_at_only else 0)

    if existing:
        values.append(user_id)
        conn.execute(
            f"UPDATE user_configs SET {', '.join(fields)} WHERE user_id = ?", values,
        )
    else:
        defaults = dict(_DEFAULT)
        if req.strategy is not None:
            defaults["strategy"] = req.strategy
        if req.system_prompt is not None:
            defaults["system_prompt"] = req.system_prompt
        if req.allowed_tools is not None:
            defaults["allowed_tools"] = json.dumps(req.allowed_tools, ensure_ascii=False)
        else:
            defaults["allowed_tools"] = None
        if req.allowed_processors is not None:
            defaults["allowed_processors"] = json.dumps(req.allowed_processors, ensure_ascii=False)
        else:
            defaults["allowed_processors"] = None
        if req.short_term_window is not None:
            defaults["short_term_window"] = req.short_term_window
        if req.group_at_only is not None:
            defaults["group_at_only"] = 1 if req.group_at_only else 0
        conn.execute(
            """INSERT INTO user_configs (user_id, strategy, system_prompt, allowed_tools,
               allowed_processors, short_term_window, group_at_only)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, defaults["strategy"], defaults["system_prompt"],
             defaults["allowed_tools"], defaults["allowed_processors"],
             defaults["short_term_window"], defaults["group_at_only"]),
        )
    conn.commit()
    return {"success": True, "user_id": user_id}


@router.delete("/{user_id}")
def reset_user_config(user_id: str):
    """删除用户配置（恢复默认）"""
    conn = db.get_connection()
    conn.execute("DELETE FROM user_configs WHERE user_id = ?", (user_id,))
    conn.commit()
    return {"success": True, "user_id": user_id}
