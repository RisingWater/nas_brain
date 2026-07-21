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

# 全局声纹缓存：[(id, user_id, np.ndarray), ...]，避免每次检测都读 DB 反序列化
_vp_cache: list[tuple[int, str, np.ndarray]] = []


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

# 确保 u_temp_voice 用户在 users 表和 user_configs 表存在
def _ensure_temp_user():
    conn = db.get_connection()
    conn.execute(
        """INSERT OR IGNORE INTO users (user_id, display_name, user_type, is_temp, is_active)
           VALUES ('u_temp_voice', '未分配声纹', 'person', 1, 1)"""
    )
    conn.execute(
        """INSERT OR IGNORE INTO user_configs (user_id, strategy)
           VALUES ('u_temp_voice', 'smart')"""
    )
    conn.commit()


_ensure_temp_user()


def _rebuild_cache():
    """从 DB 重建声纹缓存"""
    global _vp_cache
    conn = db.get_connection()
    rows = conn.execute("SELECT id, user_id, vector FROM voiceprints").fetchall()
    _vp_cache = [(r["id"], r["user_id"], np.frombuffer(r["vector"], dtype=np.float32)) for r in rows]


_rebuild_cache()


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
_AUTO_MAX_COUNT = 100  # 自动注册声纹上限


@router.post("/enroll", status_code=201)
def enroll_voiceprint(req: VoiceprintEnrollRequest):
    """注册声纹，自动注册超 100 条时清理最旧的"""
    conn = db.get_connection()
    vec_bytes = _serialize_vector(req.vector)
    try:
        cursor = conn.execute(
            "INSERT INTO voiceprints (user_id, vector, audio_path, vp_type) VALUES (?, ?, ?, ?)",
            (req.user_id, vec_bytes, req.audio_path, req.vp_type),
        )
        new_id = cursor.lastrowid

        # 自动注册超上限时清理最旧的 auto 声纹
        if req.vp_type == "auto":
            count = conn.execute(
                "SELECT COUNT(*) FROM voiceprints WHERE user_id = ? AND vp_type = 'auto'",
                (req.user_id,),
            ).fetchone()[0]
            if count > _AUTO_MAX_COUNT:
                # 保留最近的 _AUTO_MAX_COUNT 条，删更旧的
                keep_ids = conn.execute(
                    """SELECT id FROM voiceprints WHERE user_id = ? AND vp_type = 'auto'
                       ORDER BY id DESC LIMIT ?""",
                    (req.user_id, _AUTO_MAX_COUNT),
                ).fetchall()
                keep_set = set(r[0] for r in keep_ids)
                conn.execute(
                    """DELETE FROM voiceprints WHERE user_id = ? AND vp_type = 'auto'
                       AND id NOT IN ({})""".format(
                        ",".join("?" * len(keep_set))
                    ),
                    (req.user_id, *keep_set),
                )

        conn.commit()
        _rebuild_cache()
        return {"success": True, "id": new_id}
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
        _rebuild_cache()
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
    """移动声纹到另一个用户（同时搬音频文件）"""
    conn = db.get_connection()
    row = conn.execute("SELECT id, audio_path FROM voiceprints WHERE id = ?", (vp_id,)).fetchone()
    if not row:
        raise HTTPException(404, "声纹不存在")

    new_audio_path = row["audio_path"]
    old_path = row["audio_path"]
    if old_path and os.path.exists(old_path):
        # 确定目标目录
        if old_path.startswith(_VOICEPRINT_DIR):
            target_dir = os.path.join(_VOICEPRINT_DIR, target_user_id)
        else:
            # data/recordings/{user_id}/xxx.wav → data/recordings/{target_user_id}/xxx.wav
            record_dir = os.getenv("RECORD_DIR", "data/recordings")
            target_dir = os.path.join(record_dir, target_user_id)

        os.makedirs(target_dir, exist_ok=True)
        fname = os.path.basename(old_path)
        dst = os.path.join(target_dir, fname)

        if os.path.normpath(os.path.dirname(old_path)) != os.path.normpath(target_dir):
            shutil.move(old_path, dst)
            # 存相对路径
            rel = os.path.relpath(dst, os.path.dirname(os.getenv("RECORD_DIR", "data/recordings")))
            new_audio_path = rel.replace(os.sep, "/")
            import logging
            logging.getLogger("voiceprints").info("移动音频: %s -> %s", old_path, new_audio_path)

    conn.execute("UPDATE voiceprints SET user_id = ?, audio_path = ? WHERE id = ?",
                 (target_user_id, new_audio_path, vp_id))
    conn.commit()
    _rebuild_cache()
    return {"success": True, "id": vp_id, "target_user_id": target_user_id, "audio_path": new_audio_path}


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
    _rebuild_cache()
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
    """上传向量，返回匹配结果（使用内存缓存）"""
    if not _vp_cache:
        return VoiceprintDetectResponse(users=[])

    query_vec = np.array(req.vector, dtype=np.float32)
    threshold = _DEFAULT_THRESHOLD
    conn = db.get_connection()
    row = conn.execute("SELECT value FROM kv_store WHERE key = ?", (_KV_THRESHOLD_KEY,)).fetchone()
    if row:
        threshold = float(row[0])

    # 按用户分组计算平均相似度（全内存，无 DB 反序列化）
    user_sims: dict[str, list[float]] = {}
    for _id, uid, stored in _vp_cache:
        sim = _cosine_similarity(query_vec, stored)
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
