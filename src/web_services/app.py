"""web_services 管理后端入口"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .routes import users

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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "web-services"}


# 静态文件 — 前端构建产物
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
_frontend_dist = os.path.normpath(_frontend_dist)

if os.path.isdir(_frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_dist, "assets")), name="assets")

    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        """SPA 路由回退 — 所有非 API 路径返回 index.html"""
        if request.url.path.startswith("/api/") or request.url.path.startswith("/health"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        index_path = os.path.join(_frontend_dist, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path, media_type="text/html")
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    @app.get("/")
    async def serve_root():
        return FileResponse(os.path.join(_frontend_dist, "index.html"), media_type="text/html")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("WEB_SERVICE_PORT", "9020"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
