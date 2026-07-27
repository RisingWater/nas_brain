"""web_services — 监控面板 + 数据备份"""
import os
import zipfile
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger("web_services.dashboard")

router = APIRouter()

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_BACKUP_DIR = os.path.join(_PROJECT_ROOT, "backup")
_STORAGE_LIMIT = 100 * 1024 * 1024 * 1024  # 100 GB

_SERVICE_PORTS = {
    "service_manager": 9022, "web_services": 9020, "db_services": 9021,
    "wechat_gateway": 9030, "brain_services": 9031, "playback_services": 9041,
    "schedule_services": 9040, "voice_gateway": 9050,
}


def _get_dir_size(path: str) -> int:
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _get_service_memory() -> dict[str, int]:
    """获取各微服务的 Python 进程内存
    匹配: 按端口从 /proc/*/cmdline 中识别服务，再读 VmRSS
    """
    mem_by_port: dict[int, int] = {}
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except OSError:
        return {}

    for pid in pids:
        try:
            cmdline = open(f"/proc/{pid}/cmdline", "rb").read().decode("utf-8", errors="replace")
        except OSError:
            continue

        # 找端口号
        port = None
        for token in cmdline.split("\0"):
            t = token.strip()
            if t.isdigit() and 9000 <= int(t) <= 9999:
                port = int(t)
                break

        if port is None or port not in _SERVICE_PORTS.values():
            continue

        try:
            for line in open(f"/proc/{pid}/status"):
                if line.startswith("VmRSS:"):
                    rss = int(line.split()[1])  # kB
                    mem_by_port[port] = max(mem_by_port.get(port, 0), rss)
                    break
        except OSError:
            continue

    # 端口 → 服务名
    port_to_name = {v: k for k, v in _SERVICE_PORTS.items()}
    result = {}
    for port, kb in mem_by_port.items():
        result[port_to_name.get(port, f"port_{port}")] = kb
    return result


def _get_service_cpu(interval_sec: float = 0.3) -> tuple[dict[str, float], float]:
    """获取各服务 CPU 使用率（psutil.Process.cpu_percent）

    Returns:
        (per_service: dict[str, float], total_pct: float)
        返回百分比（多核累加，200% = 用了2核）
    """
    import psutil as _psutil

    port_to_name = {v: k for k, v in _SERVICE_PORTS.items()}

    def _identify_pids() -> dict[int, int]:
        """遍历进程，按 cmdline 中的端口号识别服务，返回 {pid: port}"""
        result: dict[int, int] = {}
        for proc in _psutil.process_iter(["pid", "cmdline"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                for token in cmdline:
                    t = token.strip()
                    if t.isdigit() and 9000 <= int(t) <= 9999:
                        port = int(t)
                        if port in _SERVICE_PORTS.values():
                            result[proc.info["pid"]] = port
                            break
            except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                continue
        return result

    try:
        pids = _identify_pids()
        if not pids:
            return {}, 0.0

        # 首次 cpu_percent(interval=0) 返回 0，作为基准
        procs = {}
        for pid, port in pids.items():
            try:
                p = _psutil.Process(pid)
                p.cpu_percent(interval=None)  # 初始化
                procs[pid] = (p, port)
            except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                continue

        import time as _time
        _time.sleep(interval_sec)

        # 第二次取值
        per_service: dict[str, float] = {}
        total_pct = 0.0
        for pid, (p, port) in procs.items():
            try:
                pct = p.cpu_percent(interval=None)  # 自上次调用的变化
            except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                continue
            if pct > 0:
                svc_name = port_to_name.get(port, f"port_{port}")
                per_service[svc_name] = per_service.get(svc_name, 0) + pct
                total_pct += pct

        total_pct = round(total_pct, 1)
        per_service = {k: round(v, 1) for k, v in per_service.items()}

        # 除以核心数，归一化为系统总 CPU 占比（0~100%）
        cores = os.cpu_count() or 1
        if cores > 1:
            total_pct = round(total_pct / cores, 1)
            per_service = {k: round(v / cores, 1) for k, v in per_service.items()}

        return per_service, total_pct

    except Exception as e:
        logger.warning("CPU 统计失败: %s", e)
        return {}, 0.0


@router.get("/dashboard/stats")
async def get_dashboard_stats():
    """汇总监控面板数据"""
    import requests as _req

    # 存储
    db_path = os.getenv("DB_PATH", os.path.join(_PROJECT_ROOT, "data", "nas_brain.db"))
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    rec_dir = os.getenv("RECORD_DIR", os.path.join(_PROJECT_ROOT, "data", "recordings"))
    audio_size = _get_dir_size(rec_dir) if os.path.isdir(rec_dir) else 0

    tts_dir = os.getenv("TTS_CACHE_DIR", os.path.join(_PROJECT_ROOT, "data", "tts_cache"))
    tts_size = _get_dir_size(tts_dir) if os.path.isdir(tts_dir) else 0

    log_dir = os.getenv("LOG_DIR", os.path.join(_PROJECT_ROOT, "data", "logs"))
    log_size = _get_dir_size(log_dir) if os.path.isdir(log_dir) else 0

    # CPU 使用率（top 方式读 /proc/[pid]/stat，区分各服务）
    cpu = {"load_1m": 0, "load_5m": 0, "load_15m": 0, "cores": 1, "pct": 0, "services": {}}
    try:
        cpu["cores"] = os.cpu_count() or 1
        try:
            loads = os.getloadavg()
            cpu["load_1m"] = loads[0]
            cpu["load_5m"] = loads[1]
            cpu["load_15m"] = loads[2]
        except (AttributeError, OSError):
            pass

        svc_cpu, total_pct = _get_service_cpu(interval_sec=0.3)
        cpu["pct"] = total_pct
        cpu["services"] = svc_cpu
    except Exception as e:
        logger.warning("CPU 统计失败: %s", e)

    # 总内存
    mem_total_kb = 8 * 1024 * 1024  # 默认 8GB
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemTotal:"):
                mem_total_kb = int(line.split()[1])
                break
    except OSError:
        pass

    # 各服务内存
    services_mem = _get_service_memory()

    # brain_services 统计
    brain = {"total_requests": 0, "total_answers": 0, "prompt_tokens": 0,
             "completion_tokens": 0, "total_tokens": 0, "uptime_seconds": 0}
    try:
        resp = _req.get("http://127.0.0.1:9031/api/agent-request/stats", timeout=5)
        if resp.status_code == 200:
            bs = resp.json()
            brain.update(bs)
            brain["total_tokens"] = bs.get("prompt_tokens", 0) + bs.get("completion_tokens", 0)
    except Exception as e:
        logger.warning("获取 brain_services 统计失败: %s", e)

    # 活跃用户
    active_users = {"5min": 0, "1hour": 0, "1day": 0}
    try:
        resp = _req.get("http://127.0.0.1:9021/api/chat-messages/active-users",
                        params={"minutes_5": 5, "minutes_60": 60, "minutes_1440": 1440}, timeout=5)
        if resp.status_code == 200:
            active_users = resp.json()
    except Exception:
        pass

    # 每日明细
    daily = []
    try:
        resp = _req.get("http://127.0.0.1:9021/api/request-traces/daily", timeout=5)
        if resp.status_code == 200:
            daily = resp.json().get("items", [])
    except Exception:
        pass

    return {
        "system": {"memory_services": services_mem, "memory_total_kb": mem_total_kb, "cpu": cpu},
        "storage": {
            "db_size": db_size, "audio_size": audio_size,
            "tts_cache_size": tts_size, "log_size": log_size,
            "limit": _STORAGE_LIMIT,
        },
        "brain": brain,
        "active_users": active_users,
        "daily": daily,
    }


# ===================== 数据备份 =====================

_BACKUP_EXCLUDE_DIRS = {"logs", "models"}


def _get_backup_path(filename: str) -> str:
    return os.path.normpath(os.path.join(_BACKUP_DIR, filename))


def _ensure_backup_dir():
    os.makedirs(_BACKUP_DIR, exist_ok=True)


@router.post("/backup/create")
async def create_backup():
    _ensure_backup_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"nas_brain_backup_{ts}.zip"
    zip_path = _get_backup_path(filename)
    data_dir = os.path.dirname(os.getenv("DB_PATH", os.path.join(_PROJECT_ROOT, "data", "nas_brain.db")))

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(data_dir):
                rel = os.path.relpath(root, data_dir)
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
    _ensure_backup_dir()
    items = []
    try:
        for f in sorted(os.listdir(_BACKUP_DIR), reverse=True):
            fp = os.path.join(_BACKUP_DIR, f)
            if os.path.isfile(fp) and f.endswith(".zip"):
                items.append({
                    "filename": f, "size": os.path.getsize(fp),
                    "created_at": datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                })
    except OSError:
        pass
    return {"items": items}


@router.get("/backup/download/{filename}")
async def download_backup(filename: str):
    safe_name = os.path.basename(filename)
    if not safe_name.endswith(".zip"):
        raise HTTPException(400, "仅支持 .zip 文件下载")
    fp = _get_backup_path(safe_name)
    if not os.path.isfile(fp):
        raise HTTPException(404, "备份文件不存在")
    return FileResponse(fp, media_type="application/zip", filename=safe_name)


@router.delete("/backup/{filename}")
async def delete_backup(filename: str):
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


@router.get("/wakeword/package")
async def package_wakeword():
    """打包正向+负向唤醒音频为 zip（用于训练）"""
    import zipfile, io, sqlite3
    _root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    db_path = os.getenv("DB_PATH", os.path.join(_root, "data", "nas_brain.db"))
    zip_buffer = io.BytesIO()
    count = 0
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        try:
            conn = sqlite3.connect(db_path)
            for row in conn.execute(
                "SELECT file_path, category FROM wakeword_records"
            ).fetchall():
                fp, cat = row
                if not os.path.isabs(fp):
                    fp = os.path.join(_root, fp)
                if os.path.exists(fp):
                    zf.write(fp, f"{cat}/{os.path.basename(fp)}")
                    count += 1
            conn.close()
        except Exception as e:
            logger.warning("打包唤醒音频失败: %s", e)
    zip_buffer.seek(0)
    logger.info("唤醒音频打包完成: %d 个文件", count)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    from fastapi.responses import Response as _Resp
    return _Resp(content=zip_buffer.getvalue(), media_type="application/zip",
                 headers={"Content-Disposition": f'attachment; filename="wakeword_package_{ts}.zip"'})
