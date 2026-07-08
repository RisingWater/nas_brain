"""service_manager — 微服务管理入口"""
import os
import logging
os.environ.setdefault("LOG_SERVER_NAME", "service_manager")

from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.common.utils import log_manager
from .manager import ServiceManager
from .routes import services as services_route

logger = logging.getLogger("service_manager")


@asynccontextmanager
async def lifespan(app: FastAPI):
    config_path = os.getenv("SERVICE_MANAGER_CONFIG", "deploy/service_config.json")
    manager = ServiceManager(config_path)
    services_route.init(manager)
    app.state.manager = manager
    logger.info("启动所有子服务...")
    manager.start_all()
    yield
    logger.info("停止所有子服务...")
    manager.stop_all()


app = FastAPI(title="微服务管理器", version="1.0.0", lifespan=lifespan)

app.include_router(services_route.router, prefix="/api/services", tags=["服务管理"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "service-manager"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("SERVICE_MANAGER_PORT", "9022"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
