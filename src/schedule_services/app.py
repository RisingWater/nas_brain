"""schedule_services — 定时任务微服务入口"""
import os
import logging
os.environ["LOG_SERVER_NAME"] = "schedule_services"

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.common.utils import log_manager
from .scheduler import Scheduler
from .routes import schedules, detectors
from .detector.plugin_manager import load_detectors

logger = logging.getLogger("schedule_services")

_scheduler: Scheduler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    logger.info("定时任务服务启动")

    # 加载 detector 插件
    count = load_detectors()
    logger.info("Detector 加载完成: %d 个", count)

    # 启动调度引擎
    _scheduler = Scheduler()
    _scheduler.start()

    yield

    if _scheduler:
        _scheduler.stop()
    logger.info("定时任务服务停止")


app = FastAPI(title="定时任务微服务", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(schedules.router, prefix="/api/schedules", tags=["定时任务管理"])
app.include_router(detectors.router, prefix="/api/detectors", tags=["Detector 管理"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "schedule-services"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("SCHEDULE_SERVICE_PORT", "9040"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
