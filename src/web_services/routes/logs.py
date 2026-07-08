"""web_services — 日志查看 API（直接读取 logs/ 目录下的日志文件）"""
import os
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Query
from src.common.utils import cfg

logger = logging.getLogger("web_services")

router = APIRouter()

_LOG_DIR = Path(cfg.LOG_DIR)


@router.get("/files")
def list_log_files():
    """列出所有日志文件"""
    if not _LOG_DIR.is_dir():
        return {"code": 200, "data": [], "message": "ok"}

    files = []
    for f in sorted(_LOG_DIR.iterdir(), reverse=True):
        if f.suffix == ".log" and f.is_file():
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "mtime": f.stat().st_mtime,
            })
    return {"code": 200, "data": files, "message": "ok"}


@router.get("/{filename:path}")
def read_log(
    filename: str,
    lines: int = Query(200, ge=1, le=2000, description="返回行数"),
    offset: int = Query(0, ge=0, description="跳过开头行数"),
    keyword: Optional[str] = Query(None, description="关键词过滤"),
    level: Optional[str] = Query(None, description="级别过滤 (INFO/WARNING/ERROR/DEBUG)"),
):
    """读取指定日志文件内容"""
    # 安全校验：防止路径穿越
    safe_path = _LOG_DIR.resolve() / filename
    if not str(safe_path.resolve()).startswith(str(_LOG_DIR.resolve())):
        from fastapi import HTTPException
        raise HTTPException(400, "非法路径")

    if not safe_path.is_file():
        from fastapi import HTTPException
        raise HTTPException(404, f"日志文件 {filename} 不存在")

    # 读取所有行
    with open(safe_path, encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()

    # 过滤
    if keyword:
        all_lines = [ln for ln in all_lines if keyword.lower() in ln.lower()]
    if level:
        level_upper = level.upper()
        all_lines = [ln for ln in all_lines if level_upper in ln]

    total = len(all_lines)

    # 分页：倒序（最新的在前），跳 offset 取 lines 条
    all_lines.reverse()
    page = all_lines[offset:offset + lines]

    return {
        "code": 200,
        "data": {
            "filename": filename,
            "total": total,
            "lines": page,
            "offset": offset,
            "returned": len(page),
        },
        "message": "ok",
    }
