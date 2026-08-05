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
    # batch 合并开关（关闭后队列消息顺序一条一条处理）
    batch_enabled: Optional[bool] = None
    # OCR
    ocr_image: Optional[bool] = None
    # 表情包
    send_bqb: Optional[bool] = None
    bqb_probability: Optional[int] = Field(None, ge=1, le=100)
    # 冰点（主动发言）
    ice_breaker_enabled: Optional[bool] = None
    ice_breaker_prompt: Optional[str] = None
    ice_breaker_trigger_minutes: Optional[int] = Field(None, ge=1)
    ice_breaker_cooldown_minutes: Optional[int] = Field(None, ge=5)
    ice_breaker_sleep_start: Optional[str] = None
    ice_breaker_sleep_end: Optional[str] = None


class UserConfigResponse(BaseModel):
    user_id: str
    strategy: str
    system_prompt: Optional[str] = ""
    allowed_tools: Optional[List[str]] = None
    allowed_processors: Optional[List[str]] = None
    short_term_window: int
    group_at_only: bool
    batch_enabled: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # OCR
    ocr_image: bool = False
    # 表情包
    send_bqb: bool = False
    bqb_probability: int = 50
    # 冰点
    ice_breaker_enabled: bool = False
    ice_breaker_prompt: str = ""
    ice_breaker_trigger_minutes: int = 15
    ice_breaker_cooldown_minutes: int = 60
    ice_breaker_sleep_start: str = "01:00"
    ice_breaker_sleep_end: str = "08:00"
