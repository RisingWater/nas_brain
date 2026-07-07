"""service_manager API 契约"""
from pydantic import BaseModel
from typing import Optional, List


class ServiceInfoResponse(BaseModel):
    name: str
    command: str
    description: str
    status: str
    pid: Optional[int] = None


class ServiceListResponse(BaseModel):
    code: int = 200
    data: List[ServiceInfoResponse]
    message: str = "ok"


class ServiceActionResponse(BaseModel):
    code: int = 200
    message: str
