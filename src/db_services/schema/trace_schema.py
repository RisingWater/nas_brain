"""请求链路追踪 Schema"""
from pydantic import BaseModel
from typing import Optional, Any


class TraceEvent(BaseModel):
    request_id: str
    protocol: str = ""
    user_id: str = ""
    stage: str = ""
    metadata: dict[str, Any] = {}


class TraceResponse(BaseModel):
    id: int
    request_id: str
    protocol: str
    user_id: str
    content: str
    stages: dict
    metadata: dict
    reply_skip: bool
    created_at: str


class TraceStatsResponse(BaseModel):
    avg_total_ms: float
    total_count: int
    skip_count: int
    protocol_breakdown: dict
    stage_avg: dict


class TraceListResponse(BaseModel):
    total: int
    items: list[TraceResponse]
