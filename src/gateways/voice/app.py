"""voice_gateway 入口 — 唤醒词检测 + 语音播放互斥"""
import os
import logging
os.environ["LOG_SERVER_NAME"] = "voice_gateway"

from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.common.utils import log_manager
from .routes import speak as speak_route
from .processor import VoiceProcessor

logger = logging.getLogger("voice_gateway")

_processor: VoiceProcessor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _processor
    _processor = VoiceProcessor()
    speak_route.set_processor(_processor)
    _processor.start()
    yield
    if _processor:
        _processor.stop()


app = FastAPI(title="语音网关", version="1.0.0", lifespan=lifespan)

app.include_router(speak_route.router, prefix="/api/voice", tags=["语音"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "voice-gateway"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("VOICE_GATEWAY_PORT", "9050"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
