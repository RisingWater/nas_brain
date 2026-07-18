"""web_services — 监控面板 + 数据备份"""
import os
import io
import json
import zipfile
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

logger = logging.getLogger("web_services.dashboard")

router = APIRouter()

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
_BACKUP_DIR = os.path.join(_PROJECT_ROOT, "backup")


# ===================== 监控面板 =====================


def _get_dir_size(path: str) -> int:
    """递归统计目录大小"""
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _get_db_stats() -> dict:
    db_path = os.path.join(_DATA_DIR, "nas_brain.db")
    try:
        size = os.path.getsize(db_path)
        return {"size": size, "path": "data/nas_brain.db"}
    except OSError:
        return {"size": 0, "path": "data/nas_brain.db"}


def _get_audio_stats() -> dict:
    """按用户分类统计录音文件"""
    rec_dir = os.getenv("RECORD_DIR", os.path.join(_DATA_DIR, "recordings"))
    if not os.path.isdir(rec_dir):
        return {"total_size": 0, "users": []}

    users = []
    total = 0
    try:
        for name in os.listdir(rec_dir):
            user_dir = os.path.join(rec_dir, name)
            if not os.path.isdir(user_dir):
                continue
            size = _get_dir_size(user_dir)
            count = len([f for f in os.listdir(user_dir) if os.path.isfile(os.path.join(user_dir, f))])
            users.append({"user_id": name, "size": size, "count": count})
            total += size
    except OSError:
        pass
    return {"total_size": total, "users": users}


def _get_system_stats() -> dict:
    """系统资源（容器内）"""
    stats = {}

    # 内存
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    # VmRSS: 12345 kB
                    stats["memory_kb"] = int(line.split()[1])
                    break
    except (OSError, ValueError):
        stats["memory_kb"] = 0

    # CPU 负载
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().strip().split()
            stats["load_1m"] = float(parts[0])
            stats["load_5m"] = float(parts[1])
            stats["load_15m"] = float(parts[2])
    except (OSError, ValueError, IndexError):
        stats["load_1m"] = 0
        stats["load_5m"] = 0
        stats["load_15m"] = 0

    return stats


@router.get("/dashboard/stats")
async def get_dashboard_stats():
    """汇总监控面板数据"""
    import requests as _req

    db_stat = _get_db_stats()
    audio_stat = _get_audio_stats()
    sys_stat = _get_system_stats()

    # TTS 缓存
    tts_dir = os.getenv("TTS_CACHE_DIR", os.path.join(_DATA_DIR, "tts_cache"))
    tts_size = _get_dir_size(tts_dir) if os.path.isdir(tts_dir) else 0

    # 日志
    log_dir = os.getenv("LOG_DIR", os.path.join(_DATA_DIR, "logs"))
    log_size = _get_dir_size(log_dir) if os.path.isdir(log_dir) else 0

    # brain_services 统计
    brain_stats = {}
    brain_total_requests = 0
    brain_total_answers = 0
    brain_prompt_tokens = 0
    brain_completion_tokens = 0
    brain_uptime = 0
    try:
        resp = _req.get("http://127.0.0.1:9031/api/agent-request/stats", timeout=5)
        if resp.status_code == 200:
            brain_stats = resp.json()
            brain_total_requests = brain_stats.get("total_requests", 0)
            brain_total_answers = brain_stats.get("total_answers", 0)
            brain_prompt_tokens = brain_stats.get("prompt_tokens", 0)
            brain_completion_tokens = brain_stats.get("completion_tokens", 0)
            brain_uptime = brain_stats.get("uptime_seconds", 0)
    except Exception as e:
        logger.warning("获取 brain_services 统计失败: %s", e)

    # 活跃用户（从 db_services 读取最近的消息）
    active_users = {"5min": 0, "1hour": 0, "1day": 0}
    try:
        resp = _req.get(
            "http://127.0.0.1:9021/api/chat-messages/active-users",
            params={"minutes_5": 5, "minutes_60": 60, "minutes_1440": 1440},
            timeout=5,
        )
        if resp.status_code == 200:
            active_users = resp.json()
    except Exception as e:
        logger.warning("获取活跃用户失败: %s", e)

    return {
        "system": {
            "memory_kb": sys_stat["memory_kb"],
            "memory_mb": round(sys_stat["memory_kb"] / 1024, 1) if sys_stat["memory_kb"] else 0,
            "load_1m": sys_stat["load_1m"],
            "load_5m": sys_stat["load_5m"],
            "load_15m": sys_stat["load_15m"],
        },
        "storage": {
            "db": db_stat,
            "audio": audio_stat,
            "tts_cache_size": tts_size,
            "log_size": log_size,
        },
        "brain": {
            "total_requests": brain_total_requests,
            "total_answers": brain_total_answers,
            "prompt_tokens": brain_prompt_tokens,
            "completion_tokens": brain_completion_tokens,
            "total_tokens": brain_prompt_tokens + brain_completion_tokens,
            "uptime_seconds": brain_uptime,
        },
        "active_users": active_users,
    }


# ===================== 数据备份 =====================

_BACKUP_EXCLUDE_DIRS = {"logs", "models"}


def _get_backup_path(filename: str) -> str:
    return os.path.normpath(os.path.join(_BACKUP_DIR, filename))


def _ensure_backup_dir():
    os.makedirs(_BACKUP_DIR, exist_ok=True)


@router.post("/backup/create")
async def create_backup():
    """打包 data/ 目录到 backup/ 目录"""
    _ensure_backup_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"nas_brain_backup_{ts}.zip"
    zip_path = _get_backup_path(filename)

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(_DATA_DIR):
                # 排除目录
                rel = os.path.relpath(root, _DATA_DIR)
                if rel == ".":
                    dirs[:] = [d for d in dirs if d not in _BACKUP_EXCLUDE_DIRS]
                    continue
                if rel.split(os.sep)[0] in _BACKUP_EXCLUDE_DIRS:
                    dirs[:] = []
                    continue

                for f in files:
                    fp = os.path.join(root, f)
                    arcname = os.path.relpath(fp, _PROJECT_ROOT)
                    zf.write(fp, arcname)

        size = os.path.getsize(zip_path)
        logger.info("备份创建成功: %s (%d bytes)", filename, size)
        return {"success": True, "filename": filename, "size": size}
    except Exception as e:
        logger.error("备份创建失败: %s", e)
        raise HTTPException(500, f"备份创建失败: {e}")


@router.get("/backup/list")
async def list_backups():
    """列出所有备份文件"""
    _ensure_backup_dir()
    items = []
    try:
        for f in sorted(os.listdir(_BACKUP_DIR), reverse=True):
            fp = os.path.join(_BACKUP_DIR, f)
            if os.path.isfile(fp) and f.endswith(".zip"):
                items.append({
                    "filename": f,
                    "size": os.path.getsize(fp),
                    "created_at": datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                })
    except OSError:
        pass
    return {"items": items}


@router.get("/backup/download/{filename}")
async def download_backup(filename: str):
    """下载备份文件"""
    # 防止路径穿越
    safe_name = os.path.basename(filename)
    if not safe_name.endswith(".zip"):
        raise HTTPException(400, "仅支持 .zip 文件下载")
    fp = _get_backup_path(safe_name)
    if not os.path.isfile(fp):
        raise HTTPException(404, "备份文件不存在")
    return FileResponse(fp, media_type="application/zip", filename=safe_name)


@router.delete("/backup/{filename}")
async def delete_backup(filename: str):
    """删除备份文件"""
    safe_name = os.path.basename(filename)
    fp = _get_backup_path(safe_name)
    if not os.path.isfile(fp):
        raise HTTPException(404, "备份文件不存在")
    try:
        os.remove(fp)
        logger.info("备份已删除: %s", safe_name)
        return {"success": True, "filename": safe_name}
    except Exception as e:
        raise HTTPException(500, f"删除失败: {e}")
