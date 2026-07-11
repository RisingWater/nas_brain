"""聊天记录 / 中期记忆 Schema — db_services 的请求/响应模型"""
from pydantic import BaseModel, Field
from typing import Optional, Any, List, Dict


class ChatMessageCreate(BaseModel):
    user_id: str = Field(..., min_length=1)
    role: str = Field(..., pattern=r"^(user|assistant|tool|processor)$")
    content: Optional[str] = None
    tool_calls: Optional[Any] = None       # JSON
    tool_name: Optional[str] = None
    tool_result: Optional[Any] = None       # JSON
    processor_name: Optional[str] = None
    protocol: str = "wechat"
    chat_type: str = "private"
    metadata: Dict[str, Any] = {}


class BatchChatMessageCreate(BaseModel):
    messages: List[ChatMessageCreate]


class ChatMessageResponse(BaseModel):
    id: int
    user_id: str
    role: str
    content: Optional[str] = None
    tool_calls: Optional[Any] = None
    tool_name: Optional[str] = None
    tool_result: Optional[Any] = None
    processor_name: Optional[str] = None
    protocol: str
    chat_type: str
    metadata: Any
    created_at: str


class ChatHistoryResponse(BaseModel):
    total: int
    messages: List[ChatMessageResponse]


class ChatSummaryCreate(BaseModel):
    user_id: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    last_msg_id: int = Field(..., ge=0)


class ChatSummaryResponse(BaseModel):
    id: int
    user_id: str
    summary: str
    last_msg_id: int
    created_at: str
