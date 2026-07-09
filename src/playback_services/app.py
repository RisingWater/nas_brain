"""playback_services — 音频播放微服务（TTS 合成 + 播放）"""
import os
import logging
os.environ["LOG_SERVER_NAME"] = "playback_services"

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.common.utils import log_manager
from .routes import speak, cache

logger = logging.getLogger("playback_services")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("音频播放服务启动")
    from .tts_engine import engine
    engine.load()
    yield
    logger.info("音频播放服务停止")


app = FastAPI(title="音频播放微服务", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(speak.router, prefix="/api/speak", tags=["语音合成与播放"])
app.include_router(cache.router, prefix="/api/tts/cache", tags=["TTS 缓存管理"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "playback-services"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PLAYBACK_SERVICE_PORT", "9041"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
