"""db_services — 声纹管理"""
import os
import shutil
import json
import numpy as np
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import Optional
from ..db_connection import db
from ..schema.voiceprint_schema import (
    VoiceprintEnrollRequest, VoiceprintResponse, VoiceprintListResponse,
    VoiceprintDetectRequest, VoiceprintDetectResponse, DetectUserResult,
)

router = APIRouter()

_KV_THRESHOLD_KEY = "voiceprint_threshold"
_DEFAULT_THRESHOLD = 0.5
_TEMP_USER_ID = "u_temp_voice"


def _init_table():
    conn = db.get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS voiceprints (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT NOT NULL,
            vector          BLOB NOT NULL,
            audio_path      TEXT DEFAULT '',
            vp_type         TEXT DEFAULT 'auto',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_vp_user ON voiceprints(user_id)")
    conn.commit()


_init_table()


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "vector": np.frombuffer(row["vector"], dtype=np.float32).tolist(),
        "audio_path": row["audio_path"],
        "vp_type": row["vp_type"],
        "created_at": row["created_at"],
    }


def _serialize_vector(v: list[float]) -> bytes:
    return np.array(v, dtype=np.float32).tobytes()


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(dot / norm) if norm > 0 else 0.0


# ---- 阈值 ----
@router.get("/threshold")
def get_threshold():
    conn = db.get_connection()
    row = conn.execute("SELECT value FROM kv_store WHERE key = ?", (_KV_THRESHOLD_KEY,)).fetchone()
    if not row:
        return {"threshold": _DEFAULT_THRESHOLD}
    return {"threshold": float(row[0])}


@router.put("/threshold")
def set_threshold(body: dict):
    t = float(body.get("threshold", _DEFAULT_THRESHOLD))
    t = max(0.0, min(1.0, t))
    conn = db.get_connection()
    conn.execute(
        """INSERT INTO kv_store (key, value, namespace, updated_at)
           VALUES (?, ?, 'voiceprint', CURRENT_TIMESTAMP)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                          updated_at = CURRENT_TIMESTAMP""",
        (_KV_THRESHOLD_KEY, str(t)),
    )
    conn.commit()
    return {"success": True, "threshold": t}


# ---- 注册 ----
@router.post("/enroll", status_code=201)
def enroll_voiceprint(req: VoiceprintEnrollRequest):
    """注册声纹"""
    conn = db.get_connection()
    vec_bytes = _serialize_vector(req.vector)
    try:
        cursor = conn.execute(
            "INSERT INTO voiceprints (user_id, vector, audio_path, vp_type) VALUES (?, ?, ?, ?)",
            (req.user_id, vec_bytes, req.audio_path, req.vp_type),
        )
        conn.commit()
        return {"success": True, "id": cursor.lastrowid}
    except Exception as e:
        raise HTTPException(400, f"注册失败: {e}")


_VOICEPRINT_DIR = os.getenv("RECORD_DIR", "data/voiceprints")


@router.post("/upload", status_code=201)
async def upload_voiceprint(user_id: str = Form(...), file: UploadFile = File(...)):
    """上传音频文件并注册声纹"""
    os.makedirs(_VOICEPRINT_DIR, exist_ok=True)
    ts = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    filename = f"{user_id}_{ts}{ext}"
    filepath = os.path.join(_VOICEPRINT_DIR, filename)
    try:
        with open(filepath, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(400, f"文件保存失败: {e}")

    conn = db.get_connection()
    vec_bytes = _serialize_vector([])
    try:
        cursor = conn.execute(
            "INSERT INTO voiceprints (user_id, vector, audio_path, vp_type) VALUES (?, ?, ?, ?)",
            (user_id, vec_bytes, filepath, "manual"),
        )
        conn.commit()
        return {"success": True, "id": cursor.lastrowid, "audio_path": filepath}
    except Exception as e:
        # 清理已保存的文件
        try: os.remove(filepath)
        except: pass
        raise HTTPException(400, f"注册失败: {e}")


# ---- 列表 ----
@router.get("")
def list_voiceprints(user_id: Optional[str] = Query(None)):
    """列出声纹，可按用户筛选"""
    conn = db.get_connection()
    if user_id:
        rows = conn.execute(
            "SELECT * FROM voiceprints WHERE user_id = ? ORDER BY vp_type DESC, id DESC",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM voiceprints ORDER BY user_id, vp_type DESC, id DESC"
        ).fetchall()
    items = []
    for r in rows:
        d = _row_to_dict(r)
        d.pop("vector", None)  # 列表时不返回向量数据
        items.append(d)
    return {"total": len(items), "items": items}


@router.get("/{vp_id}")
def get_voiceprint(vp_id: int):
    conn = db.get_connection()
    row = conn.execute("SELECT * FROM voiceprints WHERE id = ?", (vp_id,)).fetchone()
    if not row:
        raise HTTPException(404, "声纹不存在")
    return _row_to_dict(row)


# ---- 移动 ----
@router.put("/{vp_id}/move")
def move_voiceprint(vp_id: int, target_user_id: str = Query(...)):
    """移动声纹到另一个用户"""
    conn = db.get_connection()
    existing = conn.execute("SELECT id FROM voiceprints WHERE id = ?", (vp_id,)).fetchone()
    if not existing:
        raise HTTPException(404, "声纹不存在")
    conn.execute("UPDATE voiceprints SET user_id = ?, vp_type = 'manual' WHERE id = ?",
                 (target_user_id, vp_id))
    conn.commit()
    return {"success": True, "id": vp_id, "target_user_id": target_user_id}


# ---- 删除 ----
@router.delete("/{vp_id}")
def delete_voiceprint(vp_id: int):
    conn = db.get_connection()
    existing = conn.execute("SELECT id, audio_path FROM voiceprints WHERE id = ?", (vp_id,)).fetchone()
    if not existing:
        raise HTTPException(404, "声纹不存在")
    # 删除音频文件
    audio_path = existing["audio_path"]
    if audio_path and os.path.exists(audio_path):
        try:
            os.remove(audio_path)
        except Exception:
            pass
    conn.execute("DELETE FROM voiceprints WHERE id = ?", (vp_id,))
    conn.commit()
    return {"success": True, "id": vp_id}


# ---- 音频播放 ----
@router.get("/{vp_id}/audio")
def get_voiceprint_audio(vp_id: int):
    conn = db.get_connection()
    row = conn.execute("SELECT audio_path FROM voiceprints WHERE id = ?", (vp_id,)).fetchone()
    if not row:
        raise HTTPException(404, "声纹不存在")
    if not row["audio_path"] or not os.path.exists(row["audio_path"]):
        raise HTTPException(404, "音频文件不存在")
    return FileResponse(row["audio_path"], media_type="audio/wav")


# ---- 检测 ----
@router.post("/detect")
def detect_voiceprint(req: VoiceprintDetectRequest):
    """上传向量，返回匹配结果"""
    conn = db.get_connection()
    rows = conn.execute("SELECT * FROM voiceprints").fetchall()
    if not rows:
        return VoiceprintDetectResponse(users=[])

    query_vec = np.array(req.vector, dtype=np.float32)
    threshold = _DEFAULT_THRESHOLD
    row = conn.execute("SELECT value FROM kv_store WHERE key = ?", (_KV_THRESHOLD_KEY,)).fetchone()
    if row:
        threshold = float(row[0])

    # 按用户分组计算平均相似度
    user_sims: dict[str, list[float]] = {}
    for r in rows:
        stored = np.frombuffer(r["vector"], dtype=np.float32)
        sim = _cosine_similarity(query_vec, stored)
        uid = r["user_id"]
        if uid not in user_sims:
            user_sims[uid] = []
        user_sims[uid].append(sim)

    # 读取用户显示名
    results = []
    best_uid = None
    best_avg = 0.0
    for uid, sims in user_sims.items():
        avg = sum(sims) / len(sims)
        name_row = conn.execute("SELECT display_name FROM users WHERE user_id = ?", (uid,)).fetchone()
        display_name = name_row[0] if name_row else uid
        results.append(DetectUserResult(
            user_id=uid, display_name=display_name,
            avg_sim=avg, count=len(sims),
        ))
        if avg > best_avg and avg >= threshold:
            best_avg = avg
            best_uid = uid

    results.sort(key=lambda x: x.avg_sim, reverse=True)
    best_name = ""
    if best_uid:
        nr = conn.execute("SELECT display_name FROM users WHERE user_id = ?", (best_uid,)).fetchone()
        best_name = nr[0] if nr else best_uid

    return VoiceprintDetectResponse(
        best_user_id=best_uid,
        best_name=best_name,
        best_avg=best_avg,
        users=results,
    )
