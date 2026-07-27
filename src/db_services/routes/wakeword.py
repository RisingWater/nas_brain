"""db_services — 唤醒词记录 + 阈值"""
import os
import glob
import json
import shutil
import zipfile
import io
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from typing import Optional
from datetime import datetime
from ..db_connection import db
from ..schema.wakeword_schema import (
    WakewordRecordCreate, WakewordRecordResponse, WakewordListResponse,
    WakewordCategoryUpdate,
)

router = APIRouter()

_KV_THRESHOLD_KEY = "wakeword_threshold"
_KV_DEBUG_THRESHOLD_KEY = "wakeword_debug_threshold"
_DEFAULT_DEBUG_THRESHOLD = 0.5
_DEFAULT_THRESHOLD = 0.7
_KV_FRAME_SAMPLES_KEY = "wakeword_frame_samples"
_DEFAULT_FRAME_SAMPLES = 3200


def _init_table():
    conn = db.get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wakeword_records (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            wakeword_id     TEXT NOT NULL UNIQUE,
            file_path       TEXT NOT NULL,
            score           REAL NOT NULL,
            category        TEXT NOT NULL DEFAULT 'unclassified',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ww_category ON wakeword_records(category)")
    conn.commit()


_init_table()


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "wakeword_id": row["wakeword_id"],
        "file_path": row["file_path"],
        "score": row["score"],
        "category": row["category"],
        "created_at": row["created_at"],
    }


# ---- 阈值 ----
@router.get("/threshold")
def get_threshold():
    """获取唤醒词阈值"""
    conn = db.get_connection()
    row = conn.execute("SELECT value FROM kv_store WHERE key = ?", (_KV_THRESHOLD_KEY,)).fetchone()
    if not row:
        return {"threshold": _DEFAULT_THRESHOLD}
    return {"threshold": float(row[0])}


@router.put("/threshold")
def set_threshold(body: dict):
    """设置唤醒词阈值"""
    threshold = float(body.get("threshold", _DEFAULT_THRESHOLD))
    threshold = max(0.0, min(1.0, threshold))
    conn = db.get_connection()
    conn.execute(
        """INSERT INTO kv_store (key, value, namespace, updated_at)
           VALUES (?, ?, 'wakeword', CURRENT_TIMESTAMP)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                          updated_at = CURRENT_TIMESTAMP""",
        (_KV_THRESHOLD_KEY, str(threshold)),
    )
    conn.commit()
    return {"success": True, "threshold": threshold}


@router.get("/debug-threshold")
def get_debug_threshold():
    """获取调试阈值"""
    conn = db.get_connection()
    row = conn.execute("SELECT value FROM kv_store WHERE key = ?", (_KV_DEBUG_THRESHOLD_KEY,)).fetchone()
    if not row:
        return {"debug_threshold": _DEFAULT_DEBUG_THRESHOLD}
    return {"debug_threshold": float(row[0])}


@router.put("/debug-threshold")
def set_debug_threshold(body: dict):
    """设置调试阈值"""
    threshold = float(body.get("debug_threshold", _DEFAULT_DEBUG_THRESHOLD))
    threshold = max(0.0, min(1.0, threshold))
    conn = db.get_connection()
    conn.execute(
        """INSERT INTO kv_store (key, value, namespace, updated_at)
           VALUES (?, ?, 'wakeword', CURRENT_TIMESTAMP)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                          updated_at = CURRENT_TIMESTAMP""",
        (_KV_DEBUG_THRESHOLD_KEY, str(threshold)),
    )
    conn.commit()
    return {"success": True, "debug_threshold": threshold}


# ---- 帧大小 ----
@router.get("/frame-samples")
def get_frame_samples():
    """获取帧大小（每次读取的采样数）"""
    conn = db.get_connection()
    row = conn.execute("SELECT value FROM kv_store WHERE key = ?", (_KV_FRAME_SAMPLES_KEY,)).fetchone()
    if not row:
        return {"frame_samples": _DEFAULT_FRAME_SAMPLES}
    return {"frame_samples": int(row[0])}


@router.put("/frame-samples")
def set_frame_samples(body: dict):
    """设置帧大小"""
    fs = int(body.get("frame_samples", _DEFAULT_FRAME_SAMPLES))
    fs = max(800, min(64000, fs))
    conn = db.get_connection()
    conn.execute(
        """INSERT INTO kv_store (key, value, namespace, updated_at)
           VALUES (?, ?, 'wakeword', CURRENT_TIMESTAMP)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                          updated_at = CURRENT_TIMESTAMP""",
        (_KV_FRAME_SAMPLES_KEY, str(fs)),
    )
    conn.commit()
    return {"success": True, "frame_samples": fs}


# ---- 静音判定 ----
_KV_SILENCE_KEY = "vad_silence_ms"
_DEFAULT_SILENCE = 1600


@router.get("/vad-silence")
def get_vad_silence():
    conn = db.get_connection()
    row = conn.execute("SELECT value FROM kv_store WHERE key = ?", (_KV_SILENCE_KEY,)).fetchone()
    if not row:
        return {"silence_ms": _DEFAULT_SILENCE}
    return {"silence_ms": int(row[0])}


@router.put("/vad-silence")
def set_vad_silence(body: dict):
    ms = int(body.get("silence_ms", _DEFAULT_SILENCE))
    ms = max(200, min(10000, ms))
    conn = db.get_connection()
    conn.execute(
        """INSERT INTO kv_store (key, value, namespace, updated_at)
           VALUES (?, ?, 'wakeword', CURRENT_TIMESTAMP)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                          updated_at = CURRENT_TIMESTAMP""",
        (_KV_SILENCE_KEY, str(ms)),
    )
    conn.commit()
    return {"success": True, "silence_ms": ms}


# ---- 记录 ----
@router.post("/records", status_code=201)
def create_record(req: WakewordRecordCreate):
    """插入一条唤醒记录"""
    conn = db.get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO wakeword_records (wakeword_id, file_path, score) VALUES (?, ?, ?)",
            (req.wakeword_id, req.file_path, req.score),
        )
        conn.commit()
        return {"success": True, "id": cursor.lastrowid}
    except Exception as e:
        raise HTTPException(400, f"创建记录失败: {e}")


@router.get("/records", response_model=WakewordListResponse)
def list_records(
    category: Optional[str] = Query(None, regex=r"^(positive|negative|unclassified)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """列出唤醒记录，支持分类筛选"""
    conn = db.get_connection()
    if category:
        where = "WHERE category = ?"
        params = [category]
    else:
        where = ""
        params = []
    total = conn.execute(f"SELECT COUNT(*) FROM wakeword_records {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM wakeword_records {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    ).fetchall()
    return WakewordListResponse(
        total=total,
        items=[WakewordRecordResponse(**_row_to_dict(r)) for r in rows],
    )


@router.get("/records/{record_id}", response_model=WakewordRecordResponse)
def get_record(record_id: int):
    """获取单条唤醒记录"""
    conn = db.get_connection()
    row = conn.execute("SELECT * FROM wakeword_records WHERE id = ?", (record_id,)).fetchone()
    if not row:
        raise HTTPException(404, "记录不存在")
    return WakewordRecordResponse(**_row_to_dict(row))


@router.put("/records/{record_id}/category")
def update_record_category(record_id: int, req: WakewordCategoryUpdate):
    """修改唤醒记录分类（positive/negative/unclassified）"""
    conn = db.get_connection()
    existing = conn.execute("SELECT id FROM wakeword_records WHERE id = ?", (record_id,)).fetchone()
    if not existing:
        raise HTTPException(404, "记录不存在")
    conn.execute("UPDATE wakeword_records SET category = ? WHERE id = ?",
                 (req.category, record_id))
    conn.commit()
    return {"success": True, "id": record_id, "category": req.category}


@router.get("/records/{record_id}/audio")
def get_record_audio(record_id: int):
    """返回唤醒音频文件流"""
    conn = db.get_connection()
    row = conn.execute("SELECT file_path FROM wakeword_records WHERE id = ?", (record_id,)).fetchone()
    if not row:
        raise HTTPException(404, "记录不存在")
    file_path = row["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(404, "音频文件不存在")
    return FileResponse(file_path, media_type="audio/wav")


@router.delete("/records/{record_id}")
def delete_record(record_id: int):
    """删除单条唤醒记录及音频文件"""
    conn = db.get_connection()
    row = conn.execute("SELECT file_path FROM wakeword_records WHERE id = ?", (record_id,)).fetchone()
    if not row:
        raise HTTPException(404, "记录不存在")
    try:
        if os.path.exists(row["file_path"]):
            os.remove(row["file_path"])
    except Exception:
        pass
    conn.execute("DELETE FROM wakeword_records WHERE id = ?", (record_id,))
    conn.commit()
    return {"success": True, "id": record_id}


@router.delete("/records/old")
def delete_old_records(before_id: Optional[int] = Query(None)):
    """清理旧记录及其音频文件"""
    conn = db.get_connection()
    if before_id:
        rows = conn.execute(
            "SELECT file_path FROM wakeword_records WHERE id <= ?", (before_id,)
        ).fetchall()
        for r in rows:
            try:
                if os.path.exists(r["file_path"]):
                    os.remove(r["file_path"])
            except Exception:
                pass
        conn.execute("DELETE FROM wakeword_records WHERE id <= ?", (before_id,))
    else:
        rows = conn.execute("SELECT file_path FROM wakeword_records").fetchall()
        for r in rows:
            try:
                if os.path.exists(r["file_path"]):
                    os.remove(r["file_path"])
            except Exception:
                pass
        conn.execute("DELETE FROM wakeword_records")
    conn.commit()
    return {"success": True}


_WAKEWORD_DIR = os.getenv("WAKEWORD_DIR", "data/wakeword")


# ---- 调试音频 ----
@router.get("/debug/list")
def list_debug_audio():
    """列出调试音频文件"""
    debug_dir = os.path.join(_WAKEWORD_DIR, "debug")
    items = []
    if os.path.isdir(debug_dir):
        for fp in sorted(glob.glob(os.path.join(debug_dir, "*.wav")), reverse=True):
            fname = os.path.basename(fp)
            parts = fname.replace(".wav", "").split("_")
            score = float(parts[-1]) if len(parts) >= 3 and parts[-1].replace(".", "").isdigit() else 0.0
            try:
                mtime = os.path.getmtime(fp)
                created = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                created = ""
            items.append({"filename": fname, "score": score, "created_at": created, "size": os.path.getsize(fp)})
    return {"items": items}


@router.get("/debug/{filename}/audio")
def get_debug_audio(filename: str):
    filepath = os.path.join(_WAKEWORD_DIR, "debug", filename)
    if not os.path.exists(filepath):
        raise HTTPException(404, "文件不存在")
    return FileResponse(filepath, media_type="audio/wav")


@router.post("/debug/{filename}/classify")
def classify_debug_audio(filename: str, req: WakewordCategoryUpdate):
    src = os.path.join(_WAKEWORD_DIR, "debug", filename)
    if not os.path.exists(src):
        raise HTTPException(404, "文件不存在")
    dst = os.path.join(_WAKEWORD_DIR, filename)
    shutil.copy2(src, dst)
    parts = filename.replace(".wav", "").split("_")
    score = float(parts[-1]) if len(parts) >= 3 and parts[-1].replace(".", "").isdigit() else 0.0
    wakeword_id = f"debug_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename[:8]}"
    conn = db.get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO wakeword_records (wakeword_id, file_path, score, category) VALUES (?, ?, ?, ?)",
            (wakeword_id, dst, score, req.category),
        )
        conn.commit()
    except Exception as e:
        raise HTTPException(400, f"创建记录失败: {e}")
    try:
        os.remove(src)
    except Exception:
        pass
    return {"success": True, "id": cursor.lastrowid, "category": req.category}


@router.delete("/debug/{filename}")
def delete_debug_audio(filename: str):
    filepath = os.path.join(_WAKEWORD_DIR, "debug", filename)
    if not os.path.exists(filepath):
        raise HTTPException(404, "文件不存在")
    os.remove(filepath)
    return {"success": True}


# ---- 打包 ----
@router.get("/package")
def package_wakeword():
    import io
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        conn = db.get_connection()
        for row in conn.execute(
            "SELECT file_path, category FROM wakeword_records WHERE category IN ('positive', 'negative')"
        ).fetchall():
            if os.path.exists(row["file_path"]):
                zf.write(row["file_path"], f"{row['category']}/{os.path.basename(row['file_path'])}")
    zip_buffer.seek(0)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    from fastapi.responses import Response as _Resp
    return _Resp(content=zip_buffer.getvalue(), media_type="application/zip",
                 headers={"Content-Disposition": f'attachment; filename="wakeword_package_{ts}.zip"'})
