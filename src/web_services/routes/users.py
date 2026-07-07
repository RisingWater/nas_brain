"""web_services 管理后台 — 用户管理路由"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from src.db_services.schema.user_schema import AddUserRequest, UpdateUserRequest
from ..clients.db_client import db_client

router = APIRouter()


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = Query(None, description="搜索 display_name / wechat_name"),
    user_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
):
    """用户列表（分页 + 搜索 + 筛选）"""
    try:
        result = db_client.list_users(
            user_type=user_type,
            keyword=keyword,
            is_active=is_active,
            page=page,
            page_size=page_size,
        )
        return {"code": 200, "data": result, "message": "ok"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"db_services 调用失败: {str(e)}")


@router.get("/{user_id}")
async def get_user(user_id: str):
    """用户详情"""
    user = db_client.get_user(user_id)
    if not user:
        raise HTTPException(404, f"用户 {user_id} 不存在")
    return {"code": 200, "data": user, "message": "ok"}


@router.post("", status_code=201)
async def create_user(req: AddUserRequest):
    """创建用户"""
    try:
        result = db_client.create_user(req)
        return {"code": 201, "data": result, "message": "创建成功"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"db_services 调用失败: {str(e)}")


@router.put("/{user_id}")
async def update_user(user_id: str, req: UpdateUserRequest):
    """编辑用户"""
    try:
        result = db_client.update_user(user_id, req)
        return {"code": 200, "data": result, "message": "更新成功"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"db_services 调用失败: {str(e)}")


@router.delete("/{user_id}")
async def delete_user(user_id: str):
    """删除用户"""
    try:
        result = db_client.delete_user(user_id)
        return {"code": 200, "data": result, "message": "删除成功"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"db_services 调用失败: {str(e)}")
