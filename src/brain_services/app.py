"""brain_services — 大脑微服务入口"""
import os
import logging
os.environ["LOG_SERVER_NAME"] = "brain_services"

from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.common.utils import log_manager
from .routes import agent, tools_mgmt
from .tools.plugin_manager import load_tools

logger = logging.getLogger("brain_services")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("加载工具插件...")
    count = load_tools()
    logger.info("工具加载完成: %d 个", count)
    yield


app = FastAPI(title="大脑微服务", version="1.0.0", lifespan=lifespan)

app.include_router(agent.router, prefix="/api/agent-request", tags=["大脑请求"])
app.include_router(tools_mgmt.router, prefix="/api/tools", tags=["工具管理"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "brain-services"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BRAIN_SERVICE_PORT", "9031"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
