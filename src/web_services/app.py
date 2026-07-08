"""web_services 管理后端入口"""
import os
os.environ["LOG_SERVER_NAME"] = "web_services"

from fastapi import FastAPI, Request
from src.common.utils import log_manager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from .routes import users, logs

app = FastAPI(title="管理后端微服务", version="1.0.0")

# CORS — 允许前端开发服务器访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(users.router, prefix="/api/admin/users", tags=["用户管理"])
app.include_router(logs.router, prefix="/api/logs", tags=["日志查看"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "web-services"}


# ---- 代理 /api/services → service_manager:9022 ----
import asyncio
import requests as _req


async def _proxy_to_sm(path: str, request: Request) -> JSONResponse:
    qs = request.url.query
    url = f"http://127.0.0.1:9022{path}"
    if qs:
        url += f"?{qs}"
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "content-length")}
    try:
        resp = await asyncio.to_thread(
            _req.request, request.method, url, data=body, headers=headers, timeout=10,
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(
            content={"code": 502, "message": f"service_manager 不可用: {e}", "data": None},
            status_code=502,
        )


@app.api_route("/api/services", methods=["GET"])
async def proxy_services_list(request: Request):
    return await _proxy_to_sm("/api/services", request)


@app.api_route("/api/services/{name}/start", methods=["POST"])
async def proxy_service_start(name: str, request: Request):
    return await _proxy_to_sm(f"/api/services/{name}/start", request)


@app.api_route("/api/services/{name}/stop", methods=["POST"])
async def proxy_service_stop(name: str, request: Request):
    return await _proxy_to_sm(f"/api/services/{name}/stop", request)


@app.api_route("/api/services/{name}/restart", methods=["POST"])
async def proxy_service_restart(name: str, request: Request):
    return await _proxy_to_sm(f"/api/services/{name}/restart", request)


# 静态文件 — 前端构建产物
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
_frontend_dist = os.path.normpath(_frontend_dist)

if os.path.isdir(_frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_dist, "assets")), name="assets")

    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        """SPA 路由回退 — 所有非 API 路径返回 index.html"""
        if request.url.path.startswith("/api/") or request.url.path.startswith("/health"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        index_path = os.path.join(_frontend_dist, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path, media_type="text/html")
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    @app.get("/")
    async def serve_root():
        return FileResponse(os.path.join(_frontend_dist, "index.html"), media_type="text/html")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("WEB_SERVICE_PORT", "9020"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
