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


# ---- 代理 /api/tools → brain_services:9031 ----
async def _proxy_to_brain(path: str, request: Request) -> JSONResponse:
    qs = request.url.query
    url = f"http://127.0.0.1:9031{path}"
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
            content={"code": 502, "message": f"brain_services 不可用: {e}", "data": None},
            status_code=502,
        )


@app.api_route("/api/tools", methods=["GET"])
async def proxy_tools_list(request: Request):
    return await _proxy_to_brain("/api/tools", request)


@app.api_route("/api/tools/load", methods=["POST"])
async def proxy_tools_load(request: Request):
    return await _proxy_to_brain("/api/tools/load", request)


@app.api_route("/api/tools/reload", methods=["POST"])
async def proxy_tools_reload(request: Request):
    return await _proxy_to_brain("/api/tools/reload", request)


@app.api_route("/api/tools/schemas", methods=["GET"])
async def proxy_tools_schemas(request: Request):
    return await _proxy_to_brain("/api/tools/schemas", request)


# ---- 代理 /api/speak → playback_services:9041 ----
async def _proxy_to_playback(path: str, request: Request) -> JSONResponse:
    qs = request.url.query
    url = f"http://127.0.0.1:9041{path}"
    if qs:
        url += f"?{qs}"
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "content-length")}
    try:
        resp = await asyncio.to_thread(
            _req.request, request.method, url, data=body, headers=headers, timeout=30,
        )
        content_type = resp.headers.get("content-type", "")
        if "audio/" in content_type:
            from fastapi.responses import Response
            return Response(content=resp.content, media_type=content_type,
                            headers=dict(resp.headers))
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(
            content={"code": 502, "message": f"playback_services 不可用: {e}", "data": None},
            status_code=502,
        )


@app.api_route("/api/speak/synthesize", methods=["POST"])
async def proxy_speak_synthesize(request: Request):
    return await _proxy_to_playback("/api/speak/synthesize", request)


@app.api_route("/api/speak/play", methods=["POST"])
async def proxy_speak_play(request: Request):
    return await _proxy_to_playback("/api/speak/play", request)


@app.api_route("/api/tts/cache", methods=["GET"])
async def proxy_tts_cache_list(request: Request):
    return await _proxy_to_playback("/api/tts/cache", request)


@app.api_route("/api/tts/cache/stats", methods=["GET"])
async def proxy_tts_cache_stats(request: Request):
    return await _proxy_to_playback("/api/tts/cache/stats", request)


@app.api_route("/api/tts/cache/{cache_id}", methods=["DELETE"])
async def proxy_tts_cache_delete(cache_id: str, request: Request):
    return await _proxy_to_playback(f"/api/tts/cache/{cache_id}", request)


@app.api_route("/api/tts/cache", methods=["DELETE"])
async def proxy_tts_cache_clear(request: Request):
    return await _proxy_to_playback("/api/tts/cache", request)


# ---- 代理 /api/schedules → schedule_services:9040 ----
async def _proxy_to_schedule(path: str, request: Request) -> JSONResponse:
    qs = request.url.query
    url = f"http://127.0.0.1:9040{path}"
    if qs:
        url += f"?{qs}"
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "content-length")}
    try:
        resp = await asyncio.to_thread(
            _req.request, request.method, url, data=body, headers=headers, timeout=15,
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(
            content={"code": 502, "message": f"schedule_services 不可用: {e}", "data": None},
            status_code=502,
        )


@app.api_route("/api/schedules", methods=["GET", "POST"])
async def proxy_schedules_root(request: Request):
    return await _proxy_to_schedule("/api/schedules", request)


@app.api_route("/api/schedules/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_schedules_path(path: str, request: Request):
    return await _proxy_to_schedule(f"/api/schedules/{path}", request)


# ---- 代理 /api/detectors → schedule_services:9040 ----
@app.api_route("/api/detectors", methods=["GET"])
async def proxy_detectors_list(request: Request):
    return await _proxy_to_schedule("/api/detectors", request)


@app.api_route("/api/detectors/reload", methods=["POST"])
async def proxy_detectors_reload(request: Request):
    return await _proxy_to_schedule("/api/detectors/reload", request)


@app.api_route("/api/detectors/load", methods=["POST"])
async def proxy_detectors_load(request: Request):
    return await _proxy_to_schedule("/api/detectors/load", request)


# ---- 代理 /api/processors → brain_services:9031 ----
# 复用已有的 _proxy_to_brain（定义在 tools 代理上方）

@app.api_route("/api/processors", methods=["GET"])
async def proxy_processors_list(request: Request):
    return await _proxy_to_brain("/api/processors", request)


@app.api_route("/api/processors/reload", methods=["POST"])
async def proxy_processors_reload(request: Request):
    return await _proxy_to_brain("/api/processors/reload", request)


@app.api_route("/api/processors/load", methods=["POST"])
async def proxy_processors_load(request: Request):
    return await _proxy_to_brain("/api/processors/load", request)


# ---- 代理 /api/admin/user-configs → db_services:9021 ----
async def _proxy_to_db(path: str, request: Request) -> JSONResponse:
    qs = request.url.query
    url = f"http://127.0.0.1:9021{path}"
    if qs:
        url += f"?{qs}"
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "content-length")}
    try:
        resp = await asyncio.to_thread(
            _req.request, request.method, url, data=body, headers=headers, timeout=15,
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(
            content={"code": 502, "message": f"db_services 不可用: {e}", "data": None},
            status_code=502,
        )


@app.api_route("/api/admin/user-configs", methods=["GET"])
async def proxy_user_configs_list(request: Request):
    return await _proxy_to_db("/api/user-configs", request)


@app.api_route("/api/admin/user-configs/{user_id}", methods=["GET", "PUT", "DELETE"])
async def proxy_user_configs_detail(user_id: str, request: Request):
    return await _proxy_to_db(f"/api/user-configs/{user_id}", request)


@app.api_route("/api/admin/chat-messages/{user_id}", methods=["GET", "DELETE"])
async def proxy_chat_messages(user_id: str, request: Request):
    return await _proxy_to_db(f"/api/chat-messages/{user_id}", request)


@app.api_route("/api/admin/chat-messages/search", methods=["GET"])
async def proxy_chat_messages_search(request: Request):
    return await _proxy_to_db("/api/chat-messages/search", request)


@app.api_route("/api/admin/chat-summaries/{user_id}/latest", methods=["GET"])
async def proxy_chat_summaries_latest(user_id: str, request: Request):
    return await _proxy_to_db(f"/api/chat-summaries/{user_id}/latest", request)


# ---- 长期记忆 API (直接读写 memory.md) ----
_MEMORY_FILE = os.getenv("MEMORY_FILE", os.path.join(os.path.dirname(__file__), "..", "..", "data", "memory.md"))


@app.get("/api/admin/memory")
async def get_long_term_memory():
    """获取长期记忆内容"""
    try:
        if os.path.exists(_MEMORY_FILE):
            with open(_MEMORY_FILE, encoding="utf-8") as f:
                content = f.read()
        else:
            content = ""
        return {"code": 200, "data": {"content": content}, "message": "ok"}
    except Exception as e:
        return {"code": 500, "data": None, "message": str(e)}


@app.put("/api/admin/memory")
async def update_long_term_memory(request: Request):
    """更新长期记忆内容（全量覆盖）"""
    try:
        body = await request.json()
        content = body.get("content", "")
        os.makedirs(os.path.dirname(_MEMORY_FILE) or ".", exist_ok=True)
        with open(_MEMORY_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        return {"code": 200, "data": {"saved": True}, "message": "ok"}
    except Exception as e:
        return {"code": 500, "data": None, "message": str(e)}


@app.get("/api/admin/chat-summaries/{user_id}/list")
async def proxy_chat_summaries_list(user_id: str, request: Request):
    """获取用户的所有中期记忆"""
    return await _proxy_to_db(f"/api/chat-summaries/{user_id}/list", request)


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
