"""AI 状态 WebSocket 实时推送管理器"""
import logging
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("web_services.ws")


class ConnectionManager:
    """管理所有 WebSocket 连接，支持广播"""

    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket):
        try:
            self._connections.remove(ws)
        except ValueError:
            pass

    async def broadcast(self, data: dict):
        """向所有连接的客户端广播状态"""
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


# 全局单例
manager = ConnectionManager()


async def ws_endpoint(websocket: WebSocket):
    """WebSocket 端点：接收前端连接，实时推送 AI 状态"""
    await manager.connect(websocket)
    try:
        while True:
            # 保持连接，接收客户端心跳/消息（不做处理，仅维持连接）
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


async def notify_state_change(data: dict):
    """收到 brain_services 状态变更通知，广播给所有 WebSocket 客户端"""
    if manager.active_count > 0:
        await manager.broadcast(data)