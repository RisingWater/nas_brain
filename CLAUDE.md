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
| rss_news | RSS 新闻资讯查询（今日时政要闻/股市财经） | | |
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

### 工具路由优先级

LLM 根据 description 自主选择工具。关键路由策略：

| 场景 | 优先工具 | 说明 |
|------|---------|------|
| 今日新闻、时政要闻、股市财经 | `rss_news` | 响应快、成本低，已有订阅数据 |
| 实时查询、补充背景、验证数据 | `web_search` | 仅当 rss_news 不够用时调用 |
| 常识/历史/科学/编程等知识 | 不调用 | LLM 自身知识即可 |

## 工具返回值中的 silent 属性

- `silent=True`：LLM 调用工具时的前缀文本（如"好嘞，我来查一下"）不播放/不展示
- `final=True`：工具结果不送回 LLM 继续处理，直接作为最终回复

## Detector 插件系统

`src/schedule_services/detector/` — 定时检测插件，主循环每 tick 调用 `process_loop()`。

### 配置机制

每个 detector 声明一个 Pydantic `ConfigModel`，自动生成 JSON Schema → 前端 SchemaForm 动态渲染：

```python
class MyConfig(BaseModel):
    interval: int = Field(600, title="运行间隔（秒）", ge=60)
    chatnames: list[str] = Field(
        ["默认群"], title="通知群聊",
        json_schema_extra={"x_source": "wechat_names"},
    )

class MyDetector(BaseDetector):
    name = "my_detector"
    interval = 600
    ConfigModel = MyConfig
```

- 配置存 `data/detector/{name}.json`，`load_config()` 在启动时读取
- `interval` 字段被调度器读取，可动态调整运行频率
- `x_source: "wechat_names"` 让前端 Select 选项自动填充用户微信名

### 配置页面

`/detectors` → 列表 → 点「配置」→ 跳转到独立详情页 `/detectors/{name}/config`，显示表单（数组项用 Collapse 折叠面板）。
保存后自动重载配置到实例变量。

### 现有 Detector

| 名称 | 说明 | 可配项 |
|------|------|--------|
| `battery` | 电池电量检测 | 检查时间、低电量阈值、通知群聊 |
| `exam` | 考试日程检查 | 运行间隔、通知群聊 |
| `dsm` | DSM 无差别提醒 | 多条规则（微信/语音通知） |
| `rss_news` | RSS 资讯获取 | 订阅源列表、拉取时间、保存目录 |

### 用户策略配置页面

`/users` → 点「配置」→ 跳转到 `/users/{userId}/config`，独立页面编辑。包含两个 Tab：

- **基础配置**：策略（smart/direct/ignore）、System Prompt、工具/处理器白名单、记忆窗口、群聊 @ 配置
- **主动发言**：开关、触发语、沉默时间、冷却间隔、免打扰时段（所有配置了微信名的用户可用，不限群）

## 主动发言引擎（Ice Breaker）

`src/brain_services/ice_breaker.py` — brain_services 后台线程，定期检查冷场并主动发言。

### 配置方式

在用户策略配置页面的「主动发言」Tab 中配置（需要用户配置了微信名称），可配置：
- **主动发言触发语**：作为用户消息发给 LLM，触发它主动说话。空则用默认（群聊"群里冷场了…"/个人"好久没聊天了…"）
- **沉默触发时间**：沉默多久后触发（默认 15 分钟）
- **冷却间隔**：两次主动发言的最短间隔（默认 60 分钟）
- **免打扰时段**：夜间不发言（默认 01:00-08:00）

支持所有配置了微信名称的用户（个人和群均可）。

### 工作流程

```
后台线程（每 30~40 分钟 tick，随机扰动 5-10 分钟）:
  1. GET /api/user-configs/ice-breaker-candidates → 启用了主动发言的用户
  2. 对每个用户:
     a. 免打扰时段检查
     b. 当天已尝试且无人回应 → 跳过
     c. 查最新消息时间 → 冷场检查
     d. 冷却检查
     e. LLM 生成（原 system_prompt + 三层记忆 + 8h内聊天记录 + 触发语）
     f. 发送到微信
```

### 关键设计

- **不修改 system_prompt**，保持人设一致；触发语作为用户消息输入
- **短期窗口设 8 小时**（正常是 30 分钟），确保冷场后仍能加载到最近聊天记录，避免发言突兀
- **群聊**自动加 `@BOT_NAME` 绕过 `group_at_only`；**个人私聊**不加 `@`，`chat_type=private`
- **不暴露工具**给 LLM（`tools=[]`），只生成纯文本
- **无人回应策略**：AI 发言后无人理睬 → `attempt_date` 标记当天，当天不再对该用户触发。次日重置
- **状态全在内存**：`last_proactive_time`、`msg_id_at_send`、`attempt_date`。重启后安全重置（不会立即触发）
- **无消息不触发**：`chat_messages` 为空时直接跳过
- **立即发言测试按钮**：用户配置页 → 主动发言 Tab → 填写触发语 → 点按钮立即生成发送

### 关键文件

| 文件 | 功能 |
|------|------|
| `src/brain_services/ice_breaker.py` | 主动发言引擎（后台循环 + 状态管理） |
| `src/brain_services/routes/ice_breaker.py` | 测试触发 API |
| `src/brain_services/app.py` | lifespan 中启动/停止 |
| `src/db_services/routes/configs.py` | 存储配置 + candidates 端点 |
| `frontend/src/pages/UserConfigDetail.tsx` | 配置 UI（含测试按钮） |

## 语音网关（voice_gateway）

`src/gateways/voice/` 微服务，端口 9050，单线程主循环驱动：

```
主循环（顺序执行，无状态跳过）:
  ├─ 1. 播放队列非空 → play_sync（阻塞到播完）
  └─ 2. 唤醒词检测
         → "我在呢" → VAD → STT → 声纹 → brain POST
         → 回到 1
```

**外部播放请求**（brain 回复、定时器通知）→ 入 `_play_queue`，主循环在回到顶部时取出串行播放。`/api/voice/speak` 不阻塞 HTTP，立即返回。

**状态常量**（仅用于外部监控，主循环不依赖状态判断）：
- `STATE_IDLE = 0` — 空闲
- `STATE_RECORDING = 1` — VAD 录音中
- `STATE_PLAYING = 2` — TTS 播放中
- `STATE_PROCESSING = 3` — STT/声纹处理中

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
| `idle` | 空闲 | agent.py（处理完）、processor.py play_sync（播完） |
| `listening` | 聆听中 | 现在由 brain_services engine.py 管理 |
| `thinking` | 思考中 | engine.py（LLM 调用前） |
| `operating` | 操作中 | llm_handler.py（工具调用时） |
| `speaking` | 说话中 | agent.py（回复就绪）、processor.py play_sync（TTS 播放时） |

### API

- `GET /api/status` — 获取当前状态
- `POST /api/status/set` — 设置状态（JSON: `{"state": "...", "speaker": ""}`）
- 前端通过 `web_services` 代理：`/api/admin/ai-status`

### 前端组件

- `frontend/src/components/AIStatusFace.tsx` — SVG 表情组件，5 种状态各有不同眼/眉/嘴形 + 颜色动画
- `frontend/src/pages/AIStatusPage.tsx` — 独立全屏页面，`?debug=1` 显示测试按钮
- 路由 `/ai-status`（独立于管理后台布局）

## 请求追踪

`src/common/utils/tracer.py` — 全链路耗时追踪，数据存 `db_services` 的 `request_traces` 表。

### 打点 API

| 函数 | 用途 | 调用方 |
|------|------|--------|
| `trace_event(request_id, stage, ...)` | 记录一个事件（带毫秒时间戳） | 各微服务 |
| `trace_content(request_id, content)` | 更新请求内容（用户说的话） | voice_gateway |
| `trace_reply(request_id, reply)` | 更新回复内容 | brain_services |

### 阶段定义

当前追踪的 stage 时间线：

```
wakeword → record_end → voiceprint_end → stt_end →
brain_receive → brain_done → tts_end → play_end
```

每个 stage 有独立毫秒时间戳，前端据此计算各阶段耗时。

### 前端 TracePage

`frontend/src/pages/TracePage.tsx` — 路由 `/traces`（管理后台「智能引擎 → 请求追踪」）。

两个视图：
- **列表** — 请求 ID、协议、用户、内容、阶段耗时摘要、SKIP 标记；支持翻页和筛选（协议、用户）
- **详情** — 点「详情」进入，显示请求元信息、各阶段耗时条（Progress 组件）、事件时间线表格

### 服务端

`src/db_services/routes/traces.py` — RESTful API：
- `POST /api/request-traces/event` — 记录事件
- `PUT /api/request-traces/{id}/content` — 更新内容
- `PUT /api/request-traces/{id}/reply` — 更新回复
- `GET /api/request-traces?limit=&offset=&protocol=&user_id=` — 列表查询
- `GET /api/request-traces/{id}` — 获取单条详情
- `DELETE /api/request-traces/{id}` — 删除
- `GET /api/request-traces/stats` — 统计数据

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
