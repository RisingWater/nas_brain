# db_services/routes/users.py
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from ..repositories.user_repository import user_repo

router = APIRouter()

class AddUserRequest(BaseModel):
    display_name: str = Field(..., min_length=1)
    user_type: str = Field("person")
    wechat_name: Optional[str] = None
    is_temp: bool = False


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    wechat_name: Optional[str] = None
    is_temp: Optional[bool] = None


class UserResponse(BaseModel):
    user_id: str
    display_name: str
    user_type: str
    wechat_name: Optional[str]
    is_temp: bool
    created_at: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("", status_code=201)
async def add_user(req: AddUserRequest):
    try:
        user_id = user_repo.add_user(
            display_name=req.display_name,
            user_type=req.user_type,
            wechat_name=req.wechat_name,
            is_temp=req.is_temp
        )
        return {"success": True, "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    user = user_repo.get_user(user_id)
    if not user:
        raise HTTPException(404, f"用户 {user_id} 不存在")
    return UserResponse(**user)


@router.get("/by-wechat", response_model=UserResponse)
async def get_user_by_wechat(wechat_name: str = Query(..., min_length=1)):
    user = user_repo.get_user_by_wechat(wechat_name)
    if not user:
        raise HTTPException(404, f"微信名 '{wechat_name}' 未找到")
    return UserResponse(**user)


@router.get("")
async def list_users(
    user_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    users = user_repo.list_users(user_type=user_type, limit=limit, offset=offset)
    all_users = user_repo.list_users(user_type=user_type)
    return {"total": len(all_users), "users": [UserResponse(**u) for u in users]}


@router.put("/{user_id}")
async def update_user(user_id: str, req: UpdateUserRequest):
    if not user_repo.get_user(user_id):
        raise HTTPException(404, f"用户 {user_id} 不存在")
    success = user_repo.update_user(
        user_id=user_id,
        display_name=req.display_name,
        wechat_name=req.wechat_name,
        is_temp=req.is_temp
    )
    return {"success": success, "user_id": user_id}


@router.delete("/{user_id}")
async def delete_user(user_id: str):
    existing = user_repo.get_user(user_id)
    if not existing:
        raise HTTPException(404, f"用户 {user_id} 不存在")
    success = user_repo.delete_user(user_id)
    return {
        "success": success,
        "user_id": user_id,
        "is_temp": existing["is_temp"],
        "action": "硬删除" if existing["is_temp"] else "软删除"
    }