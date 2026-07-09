"""定时任务模块 Schema — db_services 的请求/响应模型"""
from pydantic import BaseModel, Field
from typing import Optional, List


class AddScheduleRequest(BaseModel):
    creator_id: str = Field(..., min_length=1, description="创建者 user_id")
    content: str = Field(..., min_length=1, max_length=2000)
    rtype: str = Field("once", pattern=r"^(once|daily|monthly)$")
    rdatetime: str = Field("", description="once: '2026-07-09 21:00', daily: '21:00', monthly: '15 21:00'")
    lunar: bool = False
    strategy: str = Field("direct", pattern=r"^(smart|direct)$")
    prompt: Optional[str] = None
    notify_type: str = Field("wechat", pattern=r"^(wechat|voice)$")
    notify_target: Optional[str] = Field(None, description="通知目标（微信名/群名），空则发给自己")


class UpdateScheduleRequest(BaseModel):
    content: Optional[str] = None
    rtype: Optional[str] = None
    rdatetime: Optional[str] = None
    lunar: Optional[bool] = None
    strategy: Optional[str] = None
    prompt: Optional[str] = None
    notify_type: Optional[str] = None
    notify_target: Optional[str] = None
    done: Optional[bool] = None


class ScheduleResponse(BaseModel):
    id: int
    creator_id: str
    content: str
    rtype: str
    rdatetime: Optional[str] = None
    lunar: bool
    strategy: str
    prompt: Optional[str] = None
    notify_type: str
    notify_target: Optional[str] = None
    done: bool
    created_at: str


class ListSchedulesResponse(BaseModel):
    total: int
    schedules: List[ScheduleResponse]
