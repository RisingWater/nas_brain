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
- `smart` — 纯 LLM + 工具调用（不经过 processor）。IMAGE 消息且用户开启 `ocr_image` 时自动图片识别（OCR + 多模态 LLM）→ 存历史 → skip 不回复
- `direct` — processor 优先处理，无命中则简单兜底回复
- `ignore` — 只记录聊天数据，不处理

### 智能图片识别

smart 模式下收到 IMAGE 消息时，若用户配置开启 `ocr_image`（前端叫「图片自动识别」，同时控制 OCR + 多模态 LLM 两条路径）：

1. 从 wechat_gateway 下载图片
2. **PaddleOCR** 提取文字（`layout_ocr_text` 按坐标重排版面，`min_confidence=0.8` 丢弃低置信度噪声）
3. OCR 文字 **>= 20 字** → 直接用作识别结果（主要内容是文字，省一次 LLM 调用）
4. OCR 文字 **< 20 字**（含空）→ 调用**多模态 LLM**（`image_recognize`，OpenCode Go mimo-v2.5）识别整图内容，OCR 文字作为辅助提示参数传入（「此图片经过 OCR，识别出来的文字是：xxx」）；LLM 失败时回退 OCR 文字
5. 用识别结果更新聊天记录的原消息（`UPDATE chat_messages SET content = ? WHERE id = ?`，标记【图片识别结果】）
6. 跳过回复（`skipped=True`），用户后续追问时 AI 从聊天历史中获取图片信息

关键文件：
- `src/common/lib/paddle_ocr.py` — PaddleOCR 客户端（`PaddleOCR` 类 + `ocr_recognize()` 便捷函数 + `layout_ocr_text()` 版面重排/置信度过滤）
- `src/common/lib/image_recognize.py` — 多模态 LLM 识别客户端（`ImageRecognizer` 类 + `image_recognize()` 便捷函数，图片压缩长边 1024 + OCR 辅助提示）
- `src/brain_services/strategy/engine.py` — `_ocr_image()` 方法（OCR → 置信度过滤 → 多模态 LLM 的编排），process()/process_batch() 中在 smart 路径内调用
- `.env` — `OCR_SERVER_URL` / `OCR_SERVER_TOKEN`（PaddleOCR）；`IMAGE_RECOGNIZE_API_URL` / `IMAGE_RECOGNIZE_API_KEY` / `IMAGE_RECOGNIZE_MODEL_NAME`（多模态 LLM）

processor 模式（direct）下 IMAGE 由处理器自行处理（如 homework 处理器调用百度 OCR），不经过此链路。

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
| ocr_image | OCR 图片文字识别 | | |
| rss_news | RSS 新闻资讯查询（今日时政要闻/股市财经） | | |
| search_chat_history | 搜索聊天记录 | ✅ | |
| run_python | 执行 Python 代码 | | ✅ |

**final 工具**：执行后直接返回结果，不送回 LLM 继续处理，但在上下文中插入假响应保持链路完整。

**final 属性按协议生效**：仅语音（VOICE）请求启用 final（VAD 收录短 + TTS 慢，延迟敏感）；微信/Web 请求禁用 final，所有工具按正常逻辑执行（容易一次触发多个工具，伪造响应容易出错，且无 TTS 对延迟不敏感）。由 `engine.py` 调用 `llm_handler.handle(final_enabled=req.protocol == ProtocolType.VOICE)` 控制。

### 处理器列表（hot-reload：`POST /api/processors/reload`）

| 处理器 | 触发条件 | 说明 |
|--------|----------|------|
| homework | IMAGE | OCR 作业图片 |
| urlsave | LINK | 链接转 DOCX 文件 |
| print | TEXT/IMAGE/FILE | CUPS 打印（仅 Linux） |

### 表情包附带（微信 smart 模式）

用户配置开启 `send_bqb` 后，smart 模式微信回复按 `bqb_probability`（百分比）概率附带一张梗图（LLM 生成 3 个关键词逐个搜索 → `src/common/lib/bqb_generator.py` 下载缓存到 `data/bqb/`）。

概率采用**保底机制**（类似网游暴击率，`src/common/lib/pity_rate.py`）：配置的 `bqb_probability` 是**数学期望**——构造时数值求解初始概率，使保底过程的长期期望精确等于配置值（连续未触发则概率递增，最多 5 次未中后必中，触发后重置）。按用户各持一个实例（`engine.py` 的 `_bqb_pity` 字典），配置概率变化时自动重建。

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
- `final=True`：工具结果不送回 LLM 继续处理，直接作为最终回复（**仅语音请求生效**，微信/Web 请求忽略 final 按正常逻辑执行）

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

`/users` → 点「配置」→ 跳转到 `/users/{userId}/config`，独立页面编辑。包含三个 Tab：

- **基础配置**：策略（smart/direct/ignore）、System Prompt、工具/处理器白名单、记忆窗口、群聊 @ 配置、批量合并开关（batch_enabled，默认关闭）
- **群成员备注**（仅群聊）：维护「群里谁是谁」的 sender→备注 映射，候选区从聊天记录一键提取（见下方「群成员备注」章节）
- **主动发言**：开关、触发语、沉默时间、冷却间隔、免打扰时段（所有配置了微信名的用户可用，不限群）

## 群成员备注（Group Members）

群聊用户在配置页「群成员备注」Tab 维护成员名单，帮助 AI 识别群消息来源人物。

- 存储：`user_configs.group_members` 列（JSON 数组 `[{"sender": "...", "remark": "..."}]`，sender 与微信备注一致）
- 候选提取：`GET /api/user-configs/{uid}/member-candidates` — 实时从聊天记录 `metadata.sender` 统计未记录的说话人（按出现次数排序），前端「从聊天记录提取」区一键添加，越聊越全
- 上下文注入：`context_builder.py` 在**所有记忆之前**注入 `【群成员备注】`（仅群聊），人物认知优先级最高，不被记忆内容误导
- 批量合并提示词中文字消息自动带 `sender: 内容` 前缀（sender 缺失时兜底"群友"）
- 前端注意：群成员 Tab 用 Form.List 管理，需 `forceRender` 常驻挂载——Tabs 惰性渲染下未激活的 Tab 不在 validateFields 结果里，保存代码 `|| []` 会提交空数组清空配置；保存时字段为 `undefined` 不提交，仅明确清空才提交 `[]`

关键文件：
| 文件 | 功能 |
|------|------|
| `src/db_services/routes/configs.py` | group_members 列兼容迁移 + member-candidates 候选端点 |
| `src/brain_services/strategy/context_builder.py` | 上下文注入 |
| `frontend/src/pages/UserConfigDetail.tsx` | 配置 UI（群成员 Tab + 候选区） |

## 每用户处理类（UserProcessor）

`src/brain_services/user_processor.py` — 每用户一个处理类，管理消息串行处理、记忆总结、主动发言三个 daemon 线程（替代原全局 summarizer/ice_breaker 线程，那两个文件已删除）。

- `UserProcessorManager` 是注册表：活跃用户懒创建；启用主动发言的用户（冷场无消息也需常驻）由 `sync_candidates()` 每 30 分钟预创建
- 用户信息（wechat_name / user_type）有缓存，缺失时补查 `/api/users/{uid}`

### 消息串行 + 多条 @ 合并

- 处理线程：smart+wechat 且 `batch_enabled` 开启时走**批量链路**。LLM 处理耗时即批次积累窗口——处理第一条时后续消息在队列堆积，处理完取出全部作为一批，多条 @ 消息合并成一条 user 消息一次 LLM、一次回复（避免各答各的内容重复）
- `_MessageQueue` 支持 peek：批量取批时队头只查看不取出，协议不同的消息留在原位（严格 FIFO）
- direct/ignore 用户或 `batch_enabled` 关闭：无论队列多少条，顺序一条一条处理（单条完整链路）
- 非 wechat 消息（voice/web）即使 batch 开启也一条一条处理

批量链路（`engine.py` 的 `process_batch()`，与单条 `process()` 完全独立）：

```
逐条记录 → 图片先识别（OCR + 多模态 LLM，结果写入聊天记录）→ 按 @ 模式分组 → 文字消息合并成一个提示词一次 LLM
```

- `group_at_only=True`（默认）：只取 @ 消息构建提示词，非 @ 消息只记录（skip 不回复）
- `group_at_only=False`：全部可答复消息（文字 + 识别成功的图片）合并
- 图片消息不拼进提示词：识别结果已写聊天记录，由 context_builder 作为历史注入（因此也不排除）
- 批内文字消息用 `exclude_msg_ids` 排除，避免上下文重复
- 批内无可合并文字（全是图片）→ 全部跳过不回复，与单条链路「图片识别后 skip」一致
- 合并提示词中文字消息带 `sender: 内容` 前缀（群聊 sender 缺失兜底"群友"）

收尾：被合并的从请求打 `merged` 事件 + `skip` 标记（`_mark_merged`）；主请求一次回复并发送。

### 记忆总结 / 主动发言线程

- 总结线程：低频 sleep（30min）增量总结，`last_msg_id` 对比无新消息零成本跳过；不写 chat_messages、无 tool 链路，与处理线程并发安全
- 破冰线程：低频 sleep（30~40min 随机扰动）冷场检查，逻辑与原 ice_breaker 一致
- 手动触发：`manager.summarize(uid)`（强制总结）/ `manager.generate_and_send(uid, name, prompt)`（立即主动发言）

关键文件：
| 文件 | 功能 |
|------|------|
| `src/brain_services/user_processor.py` | 每用户处理类 + 管理器（批量/总结/破冰） |
| `src/brain_services/strategy/engine.py` | `process()` 单条链路 / `process_batch()` 批量链路 |
| `src/brain_services/gateway_sender.py` | 微信/语音发送函数（agent.py 收窄后迁出） |
| `src/brain_services/routes/agent.py` | 入队路由（不再直接处理） |
| `src/brain_services/app.py` | lifespan 中 manager.start()/stop() |

## 主动发言引擎（Ice Breaker）

`src/brain_services/user_processor.py` — 每用户破冰线程（`_ice_breaker_loop` / `_check_ice_breaker`，原 `ice_breaker.py` 逻辑迁移至此），定期检查冷场并主动发言。

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
| `src/brain_services/user_processor.py` | 破冰逻辑（`_ice_breaker_loop` / `_check_ice_breaker`，状态在 `_ib_state`） |
| `src/brain_services/routes/ice_breaker.py` | 测试触发 API（转发 `manager.generate_and_send`） |
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
- 消息入队到该用户的 `UserProcessor`，实际处理在其后台处理线程运行（processor → LLM + tools）
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

### 打点 API（严格参数，不可随意加字段）

| 函数 | 用途 |
|------|------|
| `trace_event(request_id, stage, metadata=None, protocol="", user_id="")` | 记录一个事件时间戳 |
| `trace_content(request_id, content)` | 更新请求内容（用户说的话） |
| `trace_reply(request_id, reply="", skip=False)` | 更新回复内容 |

⚠️ **`trace_event` 只有 5 个形参**：`request_id`、`stage`、`metadata`、`protocol`、`user_id`。**不要传 `score`、`speaker` 等不在签名里的字段**，会 TypeError 崩溃。这些数据请放 `metadata` 字典里：

```python
# ✅ 正确
trace_event(req_id, "voiceprint_end", metadata={"speaker": "张三", "score": 0.85})

# ❌ 错误 — score 不是合法参数，会报错
trace_event(req_id, "wakeword", score=0.9)
```

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
