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
    "batch_enabled": False,
    "group_members": [],
    "ocr_image": False,
    "send_bqb": False,
    "bqb_probability": 50,
    "ice_breaker_enabled": False,
    "ice_breaker_prompt": "",
    "ice_breaker_trigger_minutes": 15,
    "ice_breaker_cooldown_minutes": 60,
    "ice_breaker_sleep_start": "01:00",
    "ice_breaker_sleep_end": "08:00",
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
    # 兼容：添加 OCR 开关列
    try:
        conn.execute("ALTER TABLE user_configs ADD COLUMN ocr_image INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass
    # 兼容：添加 batch 合并开关列（默认关闭，开启后队列消息合并处理）
    try:
        conn.execute("ALTER TABLE user_configs ADD COLUMN batch_enabled INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass
    # 兼容：添加群成员备注列（JSON: [{"sender": "...", "remark": "..."}]）
    try:
        conn.execute("ALTER TABLE user_configs ADD COLUMN group_members TEXT DEFAULT '[]'")
        conn.commit()
    except Exception:
        pass
    # 兼容：添加表情包列
    try:
        conn.execute("ALTER TABLE user_configs ADD COLUMN send_bqb INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE user_configs ADD COLUMN bqb_probability INTEGER DEFAULT 50")
        conn.commit()
    except Exception:
        pass
    # 兼容：添加冰点配置列
    for col, dtype in [
        ("ice_breaker_enabled", "INTEGER DEFAULT 0"),
        ("ice_breaker_prompt", "TEXT DEFAULT ''"),
        ("ice_breaker_trigger_minutes", "INTEGER DEFAULT 15"),
        ("ice_breaker_cooldown_minutes", "INTEGER DEFAULT 60"),
        ("ice_breaker_sleep_start", "TEXT DEFAULT '01:00'"),
        ("ice_breaker_sleep_end", "TEXT DEFAULT '08:00'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE user_configs ADD COLUMN {col} {dtype}")
            conn.commit()
        except Exception:
            pass
    conn.commit()


_init_table()


def _parse_json_list(raw) -> list:
    """解析 JSON 数组列（空/损坏时返回空列表）"""
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _row_to_dict(row) -> dict:
    return {
        "user_id": row["user_id"] or "",
        "strategy": row["strategy"] or "ignore",
        "system_prompt": row["system_prompt"] or "",
        "allowed_tools": json.loads(row["allowed_tools"]) if row["allowed_tools"] else None,
        "allowed_processors": json.loads(row["allowed_processors"]) if row["allowed_processors"] else None,
        "short_term_window": row["short_term_window"] or 30,
        "group_at_only": bool(row["group_at_only"]) if row["group_at_only"] is not None else True,
        "batch_enabled": bool(row["batch_enabled"]) if row["batch_enabled"] is not None else False,
        "group_members": _parse_json_list(row["group_members"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "ocr_image": bool(row["ocr_image"]) if row["ocr_image"] is not None else False,
        "send_bqb": bool(row["send_bqb"]) if row["send_bqb"] is not None else False,
        "bqb_probability": row["bqb_probability"] or 50,
        "ice_breaker_enabled": bool(row["ice_breaker_enabled"]) if row["ice_breaker_enabled"] is not None else False,
        "ice_breaker_prompt": row["ice_breaker_prompt"] or "",
        "ice_breaker_trigger_minutes": row["ice_breaker_trigger_minutes"] or 15,
        "ice_breaker_cooldown_minutes": row["ice_breaker_cooldown_minutes"] or 60,
        "ice_breaker_sleep_start": row["ice_breaker_sleep_start"] or "01:00",
        "ice_breaker_sleep_end": row["ice_breaker_sleep_end"] or "08:00",
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


@router.get("/ice-breaker-candidates")
def get_ice_breaker_candidates():
    """返回所有启用了主动发言且配置了微信名的用户（供 brain_services 后台循环使用）"""
    conn = db.get_connection()
    rows = conn.execute(
        """SELECT uc.*, u.wechat_name, u.user_type FROM user_configs uc
           JOIN users u ON uc.user_id = u.user_id
           WHERE u.wechat_name IS NOT NULL AND u.wechat_name != ''
             AND uc.ice_breaker_enabled = 1
           ORDER BY uc.updated_at DESC""",
    ).fetchall()
    items = []
    for r in rows:
        d = _row_to_dict(r)
        d["wechat_name"] = r["wechat_name"] or ""
        d["user_type"] = r["user_type"] or ""
        items.append(d)
    return {"items": items}


@router.get("/{user_id}", response_model=UserConfigResponse)
def get_user_config(user_id: str):
    """获取用户配置（不存在则返回默认值）"""
    conn = db.get_connection()
    row = conn.execute("SELECT * FROM user_configs WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return UserConfigResponse(user_id=user_id, **_DEFAULT)
    return UserConfigResponse(**_row_to_dict(row))


@router.get("/{user_id}/member-candidates")
def get_member_candidates(user_id: str, limit: int = 1000):
    """从聊天记录提取未记录的群成员（备选，供前端一键添加）

    遍历最近聊天记录中 user 角色的 metadata.sender，排除已配置的
    群成员备注，按出现次数排序返回。
    """
    conn = db.get_connection()
    # 已配置的 sender
    configured = set()
    cfg_row = conn.execute(
        "SELECT group_members FROM user_configs WHERE user_id = ?", (user_id,),
    ).fetchone()
    if cfg_row and cfg_row["group_members"]:
        try:
            for m in json.loads(cfg_row["group_members"]):
                if isinstance(m, dict) and m.get("sender"):
                    configured.add(m["sender"].strip())
        except Exception:
            pass
    # 统计聊天记录中未配置的 sender
    rows = conn.execute(
        """SELECT metadata FROM chat_messages
           WHERE user_id = ? AND role = 'user'
           ORDER BY id DESC LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    counter: dict[str, int] = {}
    for r in rows:
        try:
            meta = json.loads(r["metadata"] or "{}")
        except Exception:
            continue
        if not isinstance(meta, dict):
            continue
        sender = (meta.get("sender") or "").strip()
        if sender and sender not in configured:
            counter[sender] = counter.get(sender, 0) + 1
    items = sorted(
        ({"sender": s, "count": c} for s, c in counter.items()),
        key=lambda x: -x["count"],
    )
    return {"items": items}


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
    if req.batch_enabled is not None:
        fields.append("batch_enabled = ?")
        values.append(1 if req.batch_enabled else 0)
    if req.group_members is not None:
        fields.append("group_members = ?")
        values.append(json.dumps(req.group_members, ensure_ascii=False))
    if req.ocr_image is not None:
        fields.append("ocr_image = ?")
        values.append(1 if req.ocr_image else 0)
    if req.send_bqb is not None:
        fields.append("send_bqb = ?")
        values.append(1 if req.send_bqb else 0)
    if req.bqb_probability is not None:
        fields.append("bqb_probability = ?")
        values.append(req.bqb_probability)
    if req.ice_breaker_enabled is not None:
        fields.append("ice_breaker_enabled = ?")
        values.append(1 if req.ice_breaker_enabled else 0)
    if req.ice_breaker_prompt is not None:
        fields.append("ice_breaker_prompt = ?")
        values.append(req.ice_breaker_prompt)
    if req.ice_breaker_trigger_minutes is not None:
        fields.append("ice_breaker_trigger_minutes = ?")
        values.append(req.ice_breaker_trigger_minutes)
    if req.ice_breaker_cooldown_minutes is not None:
        fields.append("ice_breaker_cooldown_minutes = ?")
        values.append(req.ice_breaker_cooldown_minutes)
    if req.ice_breaker_sleep_start is not None:
        fields.append("ice_breaker_sleep_start = ?")
        values.append(req.ice_breaker_sleep_start)
    if req.ice_breaker_sleep_end is not None:
        fields.append("ice_breaker_sleep_end = ?")
        values.append(req.ice_breaker_sleep_end)

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
        # OCR 字段
        if hasattr(req, "ocr_image") and req.ocr_image is not None:
            defaults["ocr_image"] = 1 if req.ocr_image else 0
        # 表情包字段
        if hasattr(req, "send_bqb") and req.send_bqb is not None:
            defaults["send_bqb"] = 1 if req.send_bqb else 0
        if hasattr(req, "bqb_probability") and req.bqb_probability is not None:
            defaults["bqb_probability"] = req.bqb_probability
        # 冰点字段
        for k in ("ice_breaker_enabled", "ice_breaker_prompt", "ice_breaker_trigger_minutes",
                  "ice_breaker_cooldown_minutes", "ice_breaker_sleep_start", "ice_breaker_sleep_end"):
            if hasattr(req, k) and getattr(req, k) is not None:
                defaults[k] = getattr(req, k)
        conn.execute(
            """INSERT INTO user_configs (user_id, strategy, system_prompt, allowed_tools,
               allowed_processors, short_term_window, group_at_only, ocr_image,
               send_bqb, bqb_probability,
               ice_breaker_enabled, ice_breaker_prompt, ice_breaker_trigger_minutes,
               ice_breaker_cooldown_minutes, ice_breaker_sleep_start, ice_breaker_sleep_end)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, defaults["strategy"], defaults["system_prompt"],
             defaults["allowed_tools"], defaults["allowed_processors"],
             defaults["short_term_window"], defaults["group_at_only"],
             1 if defaults["ocr_image"] else 0,
             1 if defaults["send_bqb"] else 0,
             defaults["bqb_probability"],
             1 if defaults["ice_breaker_enabled"] else 0,
             defaults["ice_breaker_prompt"], defaults["ice_breaker_trigger_minutes"],
             defaults["ice_breaker_cooldown_minutes"],
             defaults["ice_breaker_sleep_start"], defaults["ice_breaker_sleep_end"]),
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
