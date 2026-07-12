"""声纹 Schema — db_services 的请求/响应模型"""
from pydantic import BaseModel, Field
from typing import Optional, List


class VoiceprintEnrollRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    vector: list[float] = Field(..., description="192维 float32 嵌入向量")
    audio_path: str = ""
    vp_type: str = "auto"


class VoiceprintResponse(BaseModel):
    id: int
    user_id: str
    audio_path: str
    vp_type: str
    created_at: str


class VoiceprintListResponse(BaseModel):
    total: int
    items: list[VoiceprintResponse]


class VoiceprintDetectRequest(BaseModel):
    vector: list[float] = Field(..., description="192维 float32 嵌入向量")


class DetectUserResult(BaseModel):
    user_id: str
    display_name: str
    avg_sim: float
    count: int


class VoiceprintDetectResponse(BaseModel):
    best_user_id: Optional[str] = None
    best_name: str = ""
    best_avg: float = 0.0
    users: list[DetectUserResult]
