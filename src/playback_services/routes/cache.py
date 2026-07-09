"""TTS 缓存管理 API — 列表/删除/统计"""
import logging
from fastapi import APIRouter, HTTPException

from ..tts_engine import engine

logger = logging.getLogger("playback_services")

router = APIRouter()


@router.get("")
def list_cache():
    """列出所有 TTS 缓存条目"""
    try:
        entries = engine.cache.list_all()
        return {"code": 200, "data": entries, "message": "ok"}
    except Exception as e:
        raise HTTPException(500, f"获取缓存列表失败: {e}")


@router.get("/stats")
def cache_stats():
    """TTS 缓存统计"""
    try:
        stats = engine.cache.stats()
        return {"code": 200, "data": stats, "message": "ok"}
    except Exception as e:
        raise HTTPException(500, f"获取缓存统计失败: {e}")


@router.delete("/{cache_id}")
def delete_cache(cache_id: str):
    """删除指定缓存条目"""
    try:
        ok = engine.cache.remove(cache_id)
        if not ok:
            raise HTTPException(404, f"缓存条目不存在: {cache_id}")
        return {"code": 200, "data": None, "message": "已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"删除缓存失败: {e}")


@router.delete("")
def clear_all_cache():
    """清空全部 TTS 缓存"""
    try:
        engine.cache.clear_all()
        return {"code": 200, "data": None, "message": "已清空"}
    except Exception as e:
        raise HTTPException(500, f"清空缓存失败: {e}")
