"""db_services — 请求链路追踪"""
import json
import time
import logging
from fastapi import APIRouter, HTTPException, Query
from ..db_connection import db
from ..schema.trace_schema import TraceEvent, TraceResponse, TraceStatsResponse, TraceListResponse

logger = logging.getLogger("db_services.traces")

router = APIRouter()


def _init_table():
    conn = db.get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS request_traces (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id      TEXT NOT NULL,
            protocol        TEXT DEFAULT '',
            user_id         TEXT DEFAULT '',
            content         TEXT DEFAULT '',
            stages          TEXT DEFAULT '{}',
            metadata        TEXT DEFAULT '{}',
            reply_skip      INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_traces_rid ON request_traces(request_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_traces_time ON request_traces(created_at)")
    conn.commit()


_init_table()


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "request_id": row["request_id"],
        "protocol": row["protocol"],
        "user_id": row["user_id"],
        "user_name": row["display_name"] or row["user_id"],
        "content": row["content"],
        "stages": json.loads(row["stages"]) if row["stages"] else {},
        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
        "reply_skip": bool(row["reply_skip"]),
        "created_at": row["created_at"],
    }


@router.post("/event", status_code=201)
def record_trace_event(event: TraceEvent):
    """记录一个追踪事件

    stage 可取值：
      brain_receive, llm_first_done, tool_call, tool_result, brain_done
      wakeword, record_end, voiceprint_end, stt_end, tts_end, play_end
    """
    conn = db.get_connection()
    existing = conn.execute(
        "SELECT id, stages, metadata FROM request_traces WHERE request_id = ?",
        (event.request_id,),
    ).fetchone()

    now_ms = int(time.time() * 1000)

    if existing:
        stages = json.loads(existing["stages"])
        metadata = json.loads(existing["metadata"])
        if event.stage:
            stages[event.stage] = now_ms
        if event.metadata:
            metadata.update(event.metadata)
        if event.protocol:
            metadata["protocol"] = event.protocol

        conn.execute(
            """UPDATE request_traces SET stages = ?, metadata = ?,
               protocol = COALESCE(NULLIF(?, ''), protocol),
               user_id = COALESCE(NULLIF(?, ''), user_id),
               content = COALESCE(NULLIF(?, ''), content)
               WHERE id = ?""",
            (json.dumps(stages), json.dumps(metadata), event.protocol,
             event.user_id, event.metadata.get("content", ""),
             existing["id"]),
        )
    else:
        stages = {event.stage: now_ms} if event.stage else {}
        metadata = dict(event.metadata)
        if event.protocol:
            metadata["protocol"] = event.protocol

        conn.execute(
            """INSERT INTO request_traces (request_id, protocol, user_id, content, stages, metadata)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event.request_id, event.protocol, event.user_id, event.metadata.get("content", ""),
             json.dumps(stages), json.dumps(metadata)),
        )

    conn.commit()


@router.put("/{request_id}/content")
def update_trace_content(request_id: str, body: dict):
    """更新请求内容（如 STT 转写结果）"""
    content = body.get("content", "")
    conn = db.get_connection()
    conn.execute("UPDATE request_traces SET content = ? WHERE request_id = ?",
                 (content, request_id))
    conn.commit()
    return {"success": True}


@router.put("/{request_id}/reply")
def update_trace_reply(request_id: str, body: dict):
    """更新回复信息（文本、是否SKIP）"""
    conn = db.get_connection()
    reply = body.get("reply", "")
    skip = body.get("skip", False)
    metadata = {}
    if reply:
        metadata["reply_summary"] = reply[:100]

    existing = conn.execute(
        "SELECT id, metadata FROM request_traces WHERE request_id = ?",
        (request_id,),
    ).fetchone()
    if existing:
        cur_meta = json.loads(existing["metadata"])
        cur_meta.update(metadata)
        conn.execute(
            "UPDATE request_traces SET metadata = ?, reply_skip = ? WHERE id = ?",
            (json.dumps(cur_meta), 1 if skip else 0, existing["id"]),
        )
    conn.commit()
    return {"success": True}


@router.get("/stats")
def get_trace_stats():
    """聚合统计"""
    conn = db.get_connection()
    rows = conn.execute("SELECT stages, protocol, reply_skip FROM request_traces").fetchall()

    total = len(rows)
    skip_count = sum(1 for r in rows if r["reply_skip"])
    protocol_count = {}
    stage_times: dict[str, list[float]] = {}
    total_times: list[float] = []

    for r in rows:
        stages = json.loads(r["stages"]) if r["stages"] else {}
        proto = r["protocol"] or "unknown"
        protocol_count[proto] = protocol_count.get(proto, 0) + 1

        if r["reply_skip"]:
            continue

        # 计算各阶段耗时
        stage_order = [
            ("brain_receive", "brain_done"),
            ("llm_first_done", "brain_done"),
            ("wakeword", "play_end"),
            ("tts_end", "play_end"),
        ]
        for start_key, end_key in stage_order:
            if start_key in stages and end_key in stages and stages[end_key] >= stages[start_key]:
                dur = stages[end_key] - stages[start_key]
                label = f"{start_key}→{end_key}"
                if label not in stage_times:
                    stage_times[label] = []
                stage_times[label].append(dur)

        # 总耗时（从最早 stage 到最晚 stage）
        timestamps = [v for v in stages.values() if isinstance(v, (int, float))]
        if len(timestamps) >= 2:
            total_times.append(max(timestamps) - min(timestamps))

    def _avg(arr):
        return round(sum(arr) / len(arr), 1) if arr else 0

    return {
        "total_count": total,
        "skip_count": skip_count,
        "protocol_breakdown": protocol_count,
        "avg_total_ms": _avg(total_times),
        "stage_avg": {k: _avg(v) for k, v in stage_times.items()},
    }


@router.get("/daily")
def get_daily_stats():
    """按天聚合：请求数、回答数、token 用量、平均耗时"""
    conn = db.get_connection()
    rows = conn.execute("""
        SELECT date(created_at) as day,
               COUNT(*) as total,
               SUM(CASE WHEN reply_skip = 0 THEN 1 ELSE 0 END) as answered,
               stages, metadata
        FROM request_traces
        GROUP BY day
        ORDER BY day DESC
        LIMIT 30
    """).fetchall()

    items = []
    for r in rows:
        stages = json.loads(r["stages"]) if r["stages"] else {}
        metadata = json.loads(r["metadata"]) if r["metadata"] else {}

        timestamps = [v for v in stages.values() if isinstance(v, (int, float))]
        avg_ms = 0
        if len(timestamps) >= 2:
            avg_ms = round(max(timestamps) - min(timestamps), 1)

        # 从 metadata 提取 token 用量（非 SKIP 的 brain_done 事件中记录）
        pt = metadata.get("prompt_tokens", 0) if isinstance(metadata, dict) else 0
        ct = metadata.get("completion_tokens", 0) if isinstance(metadata, dict) else 0
        # fallback: 可能 metadata 是 list 或旧格式
        if isinstance(metadata, list):
            pt = sum(m.get("prompt_tokens", 0) for m in metadata)
            ct = sum(m.get("completion_tokens", 0) for m in metadata)

        items.append({
            "date": r["day"],
            "total": r["total"],
            "answered": r["answered"],
            "avg_ms": avg_ms,
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": pt + ct,
        })

    return {"items": items}


@router.get("")
def list_traces(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    protocol: str = Query(None),
    user_id: str = Query(None, description="按用户 ID 筛选"),
    skip_skip: bool = Query(False, description="过滤掉 SKIP 的记录"),
):
    """分页列出追踪记录"""
    conn = db.get_connection()
    conditions = []
    params = []
    if protocol:
        conditions.append("t.protocol = ?")
        params.append(protocol)
    if user_id:
        conditions.append("t.user_id = ?")
        params.append(user_id)
    if skip_skip:
        conditions.append("t.reply_skip = 0")
    where = " AND ".join(conditions) if conditions else "1=1"

    total = conn.execute(f"SELECT COUNT(*) FROM request_traces WHERE {where}", params).fetchone()[0]
    rows = conn.execute(
        f"""SELECT t.*, COALESCE(u.display_name, '') as display_name
            FROM request_traces t
            LEFT JOIN users u ON t.user_id = u.user_id
            WHERE {where} ORDER BY t.id DESC LIMIT ? OFFSET ?""",
        (*params, limit, offset),
    ).fetchall()

    return {"total": total, "items": [_row_to_dict(r) for r in rows]}


@router.delete("/{request_id}")
def delete_trace(request_id: str):
    """删除单条追踪记录"""
    conn = db.get_connection()
    conn.execute("DELETE FROM request_traces WHERE request_id = ?", (request_id,))
    conn.commit()
    return {"success": True}


@router.get("/{request_id}")
def get_trace(request_id: str):
    """获取单个追踪记录"""
    conn = db.get_connection()
    row = conn.execute(
        """SELECT t.*, COALESCE(u.display_name, '') as display_name
           FROM request_traces t
           LEFT JOIN users u ON t.user_id = u.user_id
           WHERE t.request_id = ?""",
        (request_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "追踪记录不存在")
    return _row_to_dict(row)
