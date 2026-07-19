# NAS Brain 开发指南

## 项目架构

```
Frontend (React+AntD+Bun+Vite)  port 5173 (dev)
      ↕ HTTP
web_services:9020  (管理后端 API，含静态文件)
      ↕ HTTP
service_manager:9022  (微服务管理器，子进程启停)
      ↕ 启动/停止子进程
db_services:9021    (数据库微服务，SQLite)
brain_services:9031 (大脑微服务，LLM+工具+处理器)
wechat_gateway:9030 (微信消息网关)
voice_gateway:9050  (语音网关，唤醒词+VAD+STT+声纹)
playback_services:9041 (音频播放/TTS)
schedule_services:9040 (定时任务)
```

- `service_manager` 是入口，启动后自动拉起所有子服务
- 每个微服务是一个独立的 FastAPI 应用，运行在单独端口
- 单机模式（SINGLETON=1）所有服务用 `127.0.0.1` 互连，环境变量覆盖端口

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
- db_services 统一返回格式：`{"success": True, "id": ...}` 或 `{"total": N, "items": [...]}`
- web_services 统一返回格式：`{"code": 200, "data": ..., "message": "ok"}`
- 错误时 raise HTTPException

### 3. 注册到 service_manager

编辑 `deploy/service_config.json` 添加一条，并更新 `src/common/utils/config_manager.py` 的 `_SERVICE_PORTS` 字典。

### 4. 前端页面（如需要）

1. `frontend/src/api/your_api.ts` — API 调用
2. `frontend/src/types/your_type.ts` — TypeScript 类型
3. `frontend/src/pages/YourPage.tsx` — 页面组件
4. `frontend/src/App.tsx` — 添加路由
5. `frontend/src/components/AdminLayout.tsx` — 添加菜单

### 5. Web 服务代理（如需要前端通过 9020 访问）

在 `src/web_services/app.py` 里添加代理路由，参考已有的 `_proxy_to_db` / `_proxy_to_brain` 函数。

## 消息来源与处理策略

| 来源 | protocol | 默认策略 | 说明 |
|------|----------|----------|------|
| 微信 | WECHAT | 按用户配置 | 群聊支持 @ 检测 |
| 语音 | VOICE | 强制 smart | 唤醒词→VAD→STT→brain→TTS |
| Web | WEB | smart | 管理后台聊天输入 |

**三种策略：**
- `smart` — processor 优先 → LLM + 工具调用
- `direct` — processor 优先 → 兜底回复
- `ignore` — 只记录聊天数据，不处理

## 三层记忆体系

| 层级 | 存储 | 说明 |
|------|------|------|
| 短期 | chat_messages 最近 N 分钟 | 完整原始消息 |
| 中期 | chat_summaries 表 | LLM 定期压缩的历史摘要 |
| 长期 | data/memory.md | 全局持久化事实 |

- `short_term_window`（分钟）同时控制短期窗口和中期总结频率
- 总结是增量式的：旧总结 + 新增消息 → 新总结

## 工具/处理器插件系统

### 工具列表（hot-reload：`POST /api/tools/reload`）

| 工具 | 说明 | silent | final |
|------|------|--------|-------|
| get_weather | 天气查询 | | |
| web_search | 网络搜索（Claude CLI） | | |
| web_fetch | 网页抓取（Claude CLI） | | |
| get_yuqiao_location | 乔宝位置 + 地图图片 | | |
| get_yuqiao_power | 乔宝电量 | | |
| list_ac | 列出空调状态 | ✅ | |
| control_ac | 控制空调 | ✅ | ✅ |
| get_tv_state | 电视状态 | ✅ | |
| control_tv | 控制电视 | ✅ | ✅ |
| control_ps5 | 开关 PS5 | ✅ | ✅ |
| open_door | 开门禁 | ✅ | ✅ |
| read_memory | 读长期记忆 | ✅ | |
| save_memory | 写长期记忆 | ✅ | |
| add_reminder | 添加提醒 | | |
| list_reminders | 列出提醒 | ✅ | |
| delete_reminder | 删除提醒 | ✅ | ✅ |
| get_volume | 获取音量 | ✅ | |
| set_volume | 设置音量 | ✅ | ✅ |
| send_wechat | 发微信消息 | | ✅ |
| send_voice | TTS 播放（经 voice_gateway） | | ✅ |
| list_exams | 列出考试 | | |
| get_exam_scores | 查考试成绩 | | |
| write_text_file | 写 txt 文件 | | ✅ |
| write_pdf_file | 写 PDF 文件 | | ✅ |
| read_text_file | 读文本文件 | ✅ | |
| read_pdf_file | 读 PDF 文件 | ✅ | |
| search_chat_history | 搜索聊天记录 | ✅ | |
| run_python | 执行 Python 代码 | | ✅ |

**final 工具**：执行后直接返回结果，不送回 LLM 继续处理，但在上下文中插入假响应保持链路完整。

### 处理器列表（hot-reload：`POST /api/processors/reload`）

| 处理器 | 触发条件 | 说明 |
|--------|----------|------|
| homework | IMAGE | OCR 作业图片 |
| urlsave | LINK | 链接转 DOCX 文件 |
| print | TEXT/IMAGE/FILE | CUPS 打印（仅 Linux） |

### 返回值格式

```python
# 工具
def execute(self, args: dict) -> dict:
    return {"text": "回复文字", "files": ["/tmp/img.png"]}
    # files 由 agent route 统一发送到微信并清理

# 处理器
def handle(self, req, ctx) -> dict | None:
    return {"reply": "回复文字"}
    # 也支持 {"reply": "...", "files": ["..."]}
```

## 工具返回值中的 silent 属性

- `silent=True`：LLM 调用工具时的前缀文本（如"好嘞，我来查一下"）不播放/不展示
- `final=True`：工具结果不送回 LLM 继续处理，直接作为最终回复

## 语音网关（voice_gateway）

`src/gateways/voice/` 微服务，端口 9050，包含完整语音对话链路：

```
唤醒词检测 → 播"我在呢" → VAD 录音 → 声纹识别 → STT → brain_services → TTS 播放
```

**状态互斥：**
- PLAYING 时 → 不检测唤醒词（不听自己说话）
- RECORDING 时 → 不播放（不污染录音）
- PROCESSING 时 → 允许播放（定时器/微信推送可打断）

**组件：**
| 文件 | 功能 | 依赖 |
|------|------|------|
| `audio_manager.py` | pyaudio 录音 + Silero VAD | pyaudio, silero-vad |
| `vad.py` | VAD 录制封装 | |
| `stt.py` | 语音转文字 | funasr (SenseVoiceSmall) |
| `voiceprint.py` | 声纹识别 | modelscope (ERes2NetV2) |
| `processor.py` | 状态机 + 唤醒词 + 全流程编排 | livekit-wakeword |

## 声纹 + 唤醒词管理

- `db_services` 的 `voiceprints` 表存储声纹嵌入向量（192维 float32）
- `wakeword_records` 表存储唤醒历史，支持 positive/negative 分类
- 阈值通过 `kv_store` 存取
- 前端支持拖拽分配声纹到用户
- `u_temp_voice`（未匹配声纹的临时用户）在 db_services 启动时自动创建到 users 表和 user_configs 表

## 服务发现（SINGLETON 模式）

- `SINGLETON=1`（默认）：所有服务连 `127.0.0.1`，端口从环境变量读取
- `SINGLETON=0`：从 `deploy/services_registry.json` 读取各服务 IP

```python
cfg.get_service_url("voice_gateway", "/api/voice/speak")
# → "http://127.0.0.1:9050/api/voice/speak"
```

## 消息异步处理

- brain_services 收到请求后立即返回 `{"text": "收到"}`
- 实际处理在后台线程运行（processor → LLM + tools）
- 处理完成后主动推送到 wechat_gateway 或 voice_gateway
- 避免长时间阻塞 HTTP 请求

## AI 状态系统

`src/brain_services/status.py` — 全局单例状态管理器，线程安全。

### 五种状态

| 状态 | 含义 | 谁设置 |
|------|------|--------|
| `idle` | 空闲 | agent.py（处理完）、speak.py（播完） |
| `listening` | 聆听中 | voice_gateway processor.py（VAD 开始） |
| `thinking` | 思考中 | engine.py（LLM 调用前）、voice processor.py（发往 brain） |
| `operating` | 操作中 | llm_handler.py（工具调用时） |
| `speaking` | 说话中 | agent.py（回复就绪）、speak.py（TTS 播放时） |

### API

- `GET /api/status` — 获取当前状态
- `POST /api/status/set` — 设置状态（JSON: `{"state": "...", "speaker": ""}`）
- 前端通过 `web_services` 代理：`/api/admin/ai-status`

### 前端组件

- `frontend/src/components/AIStatusFace.tsx` — SVG 表情组件，5 种状态各有不同眼/眉/嘴形 + 颜色动画
- `frontend/src/pages/AIStatusPage.tsx` — 独立全屏页面，`?debug=1` 显示测试按钮
- 路由 `/ai-status`（独立于管理后台布局）

## 关键端口

| 服务 | 端口 | 状态 |
|------|------|------|
| service_manager | 9022 | ✅ |
| web_services | 9020 | ✅ |
| db_services | 9021 | ✅ |
| wechat_gateway | 9030 | ✅（收+发）|
| brain_services | 9031 | ✅（策略引擎就绪）|
| schedule_services | 9040 | ✅ |
| playback_services | 9041 | ✅ |
| voice_gateway | 9050 | ✅（需部署测试）|

## Docker 部署

```bash
# 构建
docker build -t nas-brain -f deploy/Dockerfile .

# 启动
deploy/run_docker.sh
```

镜像基于 `ubuntu:24.04`，包含：Python、Node.js、Bun、Claude CLI、CUPS、PulseAudio、LibreOffice。

数据通过卷挂载到 `/workdir`，`data/` 目录包含所有持久化数据（DB、日志、音频、TTS 缓存等）。

## 提交规范

commit message 用中文写。
