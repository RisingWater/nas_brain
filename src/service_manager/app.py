"""service_manager — 微服务管理入口"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .manager import ServiceManager
from .routes import services as services_route


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: 读取配置并启动所有服务
    config_path = os.getenv("SERVICE_MANAGER_CONFIG", "deploy/service_config.json")
    manager = ServiceManager(config_path)
    services_route.init(manager)
    app.state.manager = manager
    print("🚀 service_manager 启动所有子服务...")
    manager.start_all()
    yield
    # shutdown: 停止所有服务
    print("🛑 service_manager 停止所有子服务...")
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
