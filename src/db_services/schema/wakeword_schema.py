"""唤醒词记录 Schema — db_services 的请求/响应模型"""
from pydantic import BaseModel, Field
from typing import Optional


class WakewordRecordCreate(BaseModel):
    wakeword_id: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    score: float = Field(..., ge=0, le=1)


class WakewordRecordResponse(BaseModel):
    id: int
    wakeword_id: str
    file_path: str
    score: float
    category: str
    created_at: str


class WakewordListResponse(BaseModel):
    total: int
    items: list[WakewordRecordResponse]


class WakewordCategoryUpdate(BaseModel):
    category: str = Field(..., pattern=r"^(positive|negative|unclassified)$")
