from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime

class ProtocolType(str, Enum):
    """协议类型"""
    WECHAT = "wechat"
    VOICE = "voice"
    WEB = "web"


class ChatType(str, Enum):
    """会话类型"""
    PRIVATE = "private"
    GROUP = "group"
    VOICE = "voice"


class ContentType(str, Enum):
    """内容类型"""
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    FILE = "file"
    VIDEO = "video"
    LINK = "link"


class AgentRequest(BaseModel):
    """Gateway → Brain 的标准化请求"""
    
    # ===== 基础信息 =====
    protocol: ProtocolType = Field(..., description="协议类型: wechat/voice")
    request_id: str = Field(..., description="请求唯一ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="请求时间")
    
    # ===== 用户/租户 =====
    chat_type: ChatType = Field(..., description="会话类型")
    user_id: str = Field(..., description="用户唯一标识符 (关联数据库中的用户信息)")
    
    # ===== 内容 =====
    content_type: ContentType = Field(..., description="内容类型")
    content: str = Field(..., description="文本内容")
    link_url: Optional[str] = Field(None, description="链接url")
    file_id: Optional[str] = Field(None, description="图片/音频/文件/视频的文件id")
    
    # ===== 元数据 =====
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

