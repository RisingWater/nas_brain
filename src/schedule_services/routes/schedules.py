"""schedule_services — 定时任务业务 API"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from ..db_client import db_client
from ..detector.base import registry

logger = logging.getLogger("schedule_services")

router = APIRouter()


def _get_reminder() -> Optional:
    """获取 reminder_detector 实例"""
    return registry.get("reminder")


def _reload_cache():
    """通知 reminder_detector 刷新缓存"""
    reminder = _get_reminder()
    if reminder:
        reminder.reload()


@router.get("")
def list_schedules(
    done: Optional[bool] = Query(None),
    rtype: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """列表（透传 db_services）"""
    try:
        # 优先从缓存读取（reminder 只缓存待执行的）
        reminder = _get_reminder()
        if reminder and done is False:
            # 直接返回内存缓存
            cached = reminder.get_cache()
            # 客户端筛选
            result = cached
            if rtype:
                result = [s for s in result if s.get("rtype") == rtype]
            if keyword:
                kw = keyword.lower()
                result = [s for s in result if kw in s.get("content", "").lower()]
            total = len(result)
            offset = (page - 1) * page_size
            page_data = result[offset:offset + page_size]
            return {
                "code": 200,
                "data": {"total": total, "schedules": page_data, "page": page, "page_size": page_size},
                "message": "ok",
            }

        # 没缓存走 db_services
        resp = db_client.list_all(done=done)
        return {"code": 200, "data": {"total": len(resp), "schedules": resp, "page": 1, "page_size": len(resp)}, "message": "ok"}
    except Exception as e:
        raise HTTPException(502, f"获取列表失败: {e}")


@router.get("/stats")
def schedule_stats():
    """统计"""
    try:
        stats = db_client.get_stats()
        return {"code": 200, "data": stats, "message": "ok"}
    except Exception as e:
        raise HTTPException(502, f"获取统计失败: {e}")


@router.post("", status_code=201)
def create_schedule(req: dict):
    """创建定时任务"""
    try:
        result = db_client.create(req)
        _reload_cache()
        return {"code": 201, "data": result, "message": "创建成功"}
    except Exception as e:
        raise HTTPException(502, f"创建失败: {e}")


@router.get("/{schedule_id}")
def get_schedule(schedule_id: int):
    """获取单个"""
    try:
        # 先从缓存查
        reminder = _get_reminder()
        if reminder:
            cached = reminder.get_cache_by_id(schedule_id)
            if cached:
                return {"code": 200, "data": cached, "message": "ok"}
        # 缓存没有走 DB
        data = db_client.get(schedule_id)
        if not data:
            raise HTTPException(404, f"schedule {schedule_id} 不存在")
        return {"code": 200, "data": data, "message": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"查询失败: {e}")


@router.put("/{schedule_id}")
def update_schedule(schedule_id: int, req: dict):
    """编辑"""
    try:
        result = db_client.update(schedule_id, req)
        _reload_cache()
        return {"code": 200, "data": result, "message": "更新成功"}
    except Exception as e:
        raise HTTPException(502, f"更新失败: {e}")


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: int):
    """删除"""
    try:
        result = db_client.delete(schedule_id)
        _reload_cache()
        return {"code": 200, "data": result, "message": "已删除"}
    except Exception as e:
        raise HTTPException(502, f"删除失败: {e}")


@router.post("/{schedule_id}/trigger")
def trigger_schedule(schedule_id: int):
    """手动触发执行"""
    try:
        reminder = _get_reminder()
        if not reminder:
            raise HTTPException(503, "reminder_detector 未加载")

        s = reminder.get_cache_by_id(schedule_id)
        if not s:
            # 从 DB 加载
            data = db_client.get(schedule_id)
            if not data:
                raise HTTPException(404, f"schedule {schedule_id} 不存在")
            s = data

        from ..detector.base import DetectorContext
        ctx = DetectorContext()

        # 复用 reminder 的分发逻辑
        reminder._dispatch(s, ctx)
        return {"code": 200, "data": None, "message": "已触发"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"触发失败: {e}")
