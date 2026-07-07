# db_services/app.py
from fastapi import FastAPI
from .routes import users
from src.common.utils import cfg
from src.common.utils import log_manager

app = FastAPI(
    title="数据库微服务",
    version="1.0.0"
)

app.include_router(users.router, prefix="/api/users", tags=["用户管理"])

@app.get("/health")
async def health():
    return {"status": "ok", "service": "db-services"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=cfg.DB_SERVICE_PORT, reload=True)