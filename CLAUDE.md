# NAS Brain 开发指南

## 项目架构

```
Frontend (React+AntD+Bun+Vite)  port 5173 (dev)
      ↕ HTTP
web_services:9020  (管理后端 API，含静态文件)
      ↕ HTTP
service_manager:9022  (微服务管理器，子进程启停)
      ↕ 启动/停止子进程
db_services:9021  (数据库微服务)
...其他微服务
```

- `service_manager` 是入口，启动后自动拉起所有子服务
- 每个微服务是一个独立的 FastAPI 应用，运行在单独端口

## 新增一个微服务的步骤

### 1. 创建微服务目录

```
src/your_service/
  __init__.py
  app.py              # FastAPI 入口
  schema/
    __init__.py
    your_schema.py    # Pydantic API 契约
  routes/
    __init__.py
    your_routes.py    # API 路由
```

### 2. 遵循的模式

**app.py** — FastAPI 入口：
```python
from fastapi import FastAPI

app = FastAPI(title="你的微服务", version="1.0.0")

# 注册路由
from .routes import your_routes
app.include_router(your_routes.router, prefix="/api/your-path")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=9xxx)
```

**schema/ — API 契约**：
- 所有请求体和响应体用 Pydantic BaseModel 定义
- 作为微服务间 HTTP 调用的类型契约

**routes/ — 路由**：
- 用 APIRouter 定义，`response_model` 引用 schema 里的模型
- 统一返回格式：`{"code": 200, "data": ..., "message": "ok"}`
- 错误时 raise HTTPException

### 3. 注册到 service_manager

编辑 `deploy/service_config.json` 添加一条：
```json
{
  "name": "your_service",
  "description": "服务说明",
  "command": "python -m uvicorn src.your_service.app:app --host 0.0.0.0 --port 9xxx"
}
```

### 4. 前端页面（如需要）

1. `frontend/src/api/your_api.ts` — API 调用
2. `frontend/src/types/your_type.ts` — TypeScript 类型
3. `frontend/src/pages/YourPage.tsx` — 页面组件
4. `frontend/src/App.tsx` — 添加路由
5. `frontend/src/components/AdminLayout.tsx` — 添加菜单

### 5. Web 服务代理（如需要前端通过 9020 访问）

如果新服务有前端页面需要调用的 API，在 `src/web_services/app.py` 里添加代理路由。

## 跨平台注意事项

- 子进程管理用 `subprocess.Popen` + `terminate()` / `kill()`，不要用 taskkill
- 路径拼接用 `os.path.join`，不要硬编码 `/` 或 `\`
- 服务间通信用 `127.0.0.1`（不用 `localhost`，避免 Windows IPv6 回退延迟）

## 关键端口

| 服务 | 端口 |
|------|------|
| service_manager | 9022 |
| web_services | 9020 |
| db_services | 9021 |
| wechat_gateway | 9030 |
| brain_services | 9031 |

## 提交规范

commit message 用中文写。
