"""用户模块 Schema — db_services 对外 API 的请求/响应模型"""
from pydantic import BaseModel, Field
from typing import Optional, List


class AddUserRequest(BaseModel):
    display_name: str = Field(..., min_length=1)
    user_type: str = Field("person")
    wechat_name: Optional[str] = None
    is_temp: bool = False


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    wechat_name: Optional[str] = None
    user_type: Optional[str] = None
    is_temp: Optional[bool] = None


class UserResponse(BaseModel):
    user_id: str
    display_name: str
    user_type: str
    wechat_name: Optional[str]
    is_temp: bool
    created_at: Optional[str] = None
    is_active: Optional[bool] = None


class ListUsersResponse(BaseModel):
    total: int
    users: List[UserResponse]
