# db_services/app.py
import os
os.environ["LOG_SERVER_NAME"] = "db_services"

from fastapi import FastAPI
from .routes import users, schedules, kv, configs, chat, summaries
from src.common.utils import cfg
from src.common.utils import log_manager

app = FastAPI(
    title="数据库微服务",
    version="1.0.0"
)

app.include_router(users.router, prefix="/api/users", tags=["用户管理"])
app.include_router(schedules.router, prefix="/api/schedules", tags=["定时任务"])
app.include_router(kv.router, prefix="/api/kv", tags=["KV 存储"])
app.include_router(configs.router, prefix="/api/user-configs", tags=["用户配置"])
app.include_router(chat.router, prefix="/api/chat-messages", tags=["聊天记录"])
app.include_router(summaries.router, prefix="/api/chat-summaries", tags=["中期记忆"])

@app.get("/health")
async def health():
    return {"status": "ok", "service": "db-services"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=cfg.DB_SERVICE_PORT, reload=True)