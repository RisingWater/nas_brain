"""wechat_gateway — 状态查看路由"""
from fastapi import APIRouter

router = APIRouter()

_message_count = 0
_last_message_time = None


def record_message():
    """记录一条已处理的消息"""
    global _message_count, _last_message_time
    from datetime import datetime
    _message_count += 1
    _last_message_time = datetime.now().isoformat()


@router.get("/status")
async def gateway_status():
    """网关运行状态"""
    return {
        "code": 200,
        "data": {
            "processed_count": _message_count,
            "last_message_at": _last_message_time,
            "service": "wechat-gateway",
        },
        "message": "ok",
    }
