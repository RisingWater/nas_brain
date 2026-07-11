"""用户策略配置 Schema — db_services 的请求/响应模型"""
from pydantic import BaseModel, Field
from typing import Optional, List


class UserConfigUpdateRequest(BaseModel):
    strategy: Optional[str] = Field(None, pattern=r"^(smart|direct|ignore)$")
    system_prompt: Optional[str] = None
    allowed_tools: Optional[List[str]] = None   # null=全部工具
    allowed_processors: Optional[List[str]] = None  # null=全部处理器
    short_term_window: Optional[int] = Field(None, ge=1, le=1440)
    group_at_only: Optional[bool] = None


class UserConfigResponse(BaseModel):
    user_id: str
    strategy: str
    system_prompt: Optional[str] = ""
    allowed_tools: Optional[List[str]] = None
    allowed_processors: Optional[List[str]] = None
    short_term_window: int
    group_at_only: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
