"""wechat_gateway — 微信消息网关入口"""
import os
import logging
os.environ.setdefault("LOG_SERVER_NAME", "wechat_gateway")

import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.common.utils import log_manager
from .routes import status, files
from .processor import WeChatProcessor

logger = logging.getLogger("wechat_gateway")

_processor: WeChatProcessor = None
_thread: threading.Thread = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _processor, _thread
    _processor = WeChatProcessor()

    _thread = threading.Thread(target=_processor.run_loop, daemon=True)
    _thread.start()
    logger.info("消息轮询已启动")

    yield

    if _processor:
        _processor.stop_loop()
    logger.info("已停止")


app = FastAPI(title="微信网关微服务", version="1.0.0", lifespan=lifespan)

app.include_router(status.router, prefix="/api/gateway", tags=["网关状态"])
app.include_router(files.router, prefix="/api/gateway", tags=["文件下载"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "wechat-gateway"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("WECHAT_GATEWAY_PORT", "9030"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
