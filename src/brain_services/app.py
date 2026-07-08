"""brain_services — 大脑微服务入口"""
import os
from fastapi import FastAPI
from .routes import agent

app = FastAPI(title="大脑微服务", version="1.0.0")

app.include_router(agent.router, prefix="/api/agent-request", tags=["大脑请求"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "brain-services"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BRAIN_SERVICE_PORT", "9031"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
