"""db_services — 用户 CRUD"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ..schema.user_schema import AddUserRequest, UpdateUserRequest, UserResponse, ListUsersResponse
from ..repositories.user_repository import user_repo
from ..db_connection import db

router = APIRouter()


@router.post("", status_code=201)
async def add_user(req: AddUserRequest):
    try:
        user_id = user_repo.add_user(
            display_name=req.display_name,
            user_type=req.user_type,
            wechat_name=req.wechat_name,
            is_temp=req.is_temp
        )
        # 自动创建默认策略配置（ignore）
        conn = db.get_connection()
        conn.execute(
            """INSERT OR IGNORE INTO user_configs (user_id, strategy)
               VALUES (?, 'ignore')""",
            (user_id,),
        )
        conn.commit()
        return {"success": True, "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/by-wechat", response_model=UserResponse)
async def get_user_by_wechat(wechat_name: str = Query(..., min_length=1)):
    """按微信名查找用户（必须放在 /{user_id} 前面）"""
    user = user_repo.get_user_by_wechat(wechat_name)
    if not user:
        raise HTTPException(404, f"微信名 '{wechat_name}' 未找到")
    return UserResponse(**user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    user = user_repo.get_user(user_id)
    if not user:
        raise HTTPException(404, f"用户 {user_id} 不存在")
    return UserResponse(**user)


@router.get("", response_model=ListUsersResponse)
async def list_users(
    user_type: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None, description="搜索 display_name 或 wechat_name"),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    users = user_repo.list_users(
        user_type=user_type, keyword=keyword,
        is_active=is_active, limit=limit, offset=offset
    )
    all_users = user_repo.list_users(
        user_type=user_type, keyword=keyword, is_active=is_active
    )
    return ListUsersResponse(
        total=len(all_users),
        users=[UserResponse(**u) for u in users]
    )


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
    # 同时删除关联数据
    conn = db.get_connection()
    conn.execute("DELETE FROM user_configs WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM chat_summaries WHERE user_id = ?", (user_id,))
    conn.commit()
    return {
        "success": success,
        "user_id": user_id,
        "is_temp": existing["is_temp"],
        "action": "硬删除" if existing["is_temp"] else "软删除"
    }
