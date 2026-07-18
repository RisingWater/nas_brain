# NAS Brain

家庭 NAS 部署的智能助手，支持微信/语音/Web 多种交互方式，集成 LLM、工具调用、声纹识别、定时任务等。

## 系统需求

### 硬件

| 组件 | 最低要求 | 推荐 |
|------|---------|------|
| CPU | 4 核 x86_64 | 8 核 |
| RAM | 8 GB | 16 GB（LLM 上下文大时） |
| 磁盘 | 20 GB | 50 GB（含模型文件） |
| 麦克风 | USB 麦克风或板载音频输入 | （语音对话需要） |
| 音箱 | 3.5mm/HDMI/USB 音频输出 | （语音对话需要） |

### 软件

- **OS**: Linux (推荐 Ubuntu 24.04) 或 Windows（部分功能受限）
- **Docker**: 24+（推荐部署方式）
- **Python**: 3.10+
- **Node.js**: 22+（前端构建）
- **Bun**: 1.x（前端构建）

### 依赖服务

| 服务 | 用途 | 必须 |
|------|------|------|
| WXAuto (微信框架) | 微信消息收发 | 否（无微信则不需要） |
| Edge TTS API | 语音合成 | 否（无语音则不需要） |
| Home Assistant | 空调/电视/PS5 控制 | 否 |
| CUPS 打印机 | 打印功能 | 否 |

## 功能

### 多端交互

- **微信** — 私聊/群聊，群聊支持 @ 检测、按用户配置策略
- **语音** — 唤醒词 → VAD 录音 → 声纹识别 → STT → LLM → TTS 完整链路
- **Web** — 管理后台（React + Ant Design），支持聊天输入

### AI 能力

- **LLM 驱动** — 支持 DeepSeek 等 API，可配置 system prompt 和工具
- **三层记忆** — 短期（原始消息）、中期（LLM 摘要）、长期（持久化事实文件）
- **策略引擎** — 每个用户可独立配置 `smart`/`direct`/`ignore` 三种策略
- **工具插件系统** — 可热加载，支持 `final` 和 `silent` 属性

### 工具列表

| 工具 | 说明 | 工具 | 说明 |
|------|------|------|------|
| get_weather | 天气查询 | list_ac / control_ac | 空调控制 |
| web_search / web_fetch | 网络搜索/抓取 | control_tv | 电视控制 |
| get_yuqiao_location / power | 儿童定位/电量 | control_ps5 | PS5 控制 |
| read_memory / save_memory | 长期记忆读写 | open_door | 智能门禁 |
| add_reminder / list / delete | 提醒管理 | send_wechat | 发微信消息 |
| get/set_volume | 音量控制 | send_voice | TTS 播放 |
| list_exams / get_scores | 查考试成绩 | run_python | 执行 Python |
| write/read_text_file / pdf | 文件读写 | search_chat_history | 聊天记录搜索 |

### 处理器（热加载）

| 处理器 | 触发 | 功能 |
|--------|------|------|
| homework | 图片 | OCR 作业识别 |
| urlsave | 链接 | 链接转 DOCX 存档 |
| print | 文本/图片/文件 | CUPS 打印 |

### 声纹识别

- 基于 ERes2NetV2 的说话人识别
- 唤醒词触发后自动录音并匹配用户
- Web 管理：拖拽分配声纹、播放录音、设置阈值
- 未匹配的语音自动归入「未分配」用户

### 其他

- 定时任务（检测器）— 考试提醒等
- TTS 缓存 — 重复文本跳过合成
- 服务管理器 — Web 上启停各微服务
- 微信聊天记录搜索

## 项目架构

```
Frontend (React+AntD+Bun+Vite)  :5173 (dev)
      ↕ HTTP
web_services:9020    (管理后端 API + 静态文件)
      ↕ HTTP
service_manager:9022 (微服务管理器，子进程启停)
      ↕ 启动/停止子进程
db_services:9021     (数据库微服务，SQLite)
brain_services:9031  (大脑微服务，LLM+工具+处理器)
wechat_gateway:9030  (微信消息网关)
voice_gateway:9050   (语音网关，唤醒词+VAD+STT+声纹)
playback_services:9041 (音频播放/TTS)
schedule_services:9040 (定时任务)
```

## 快速开始

### Docker 部署

```bash
# 1. 克隆代码
git clone <repo> && cd nas_brain

# 2. 配置
cp .env.example .env
# 修改 .env：填入 API Key、微信地址、Home Assistant 地址等

# 3. 构建
docker build -t nas-brain -f deploy/Dockerfile .

# 4. 启动
deploy/run_docker.sh
```

容器启动后：
- 管理后台：http://localhost:9020
- CUPS 打印管理：http://localhost:631

环境变量和持久数据（DB、日志、音频、TTS 缓存等）通过卷挂载到 `/workdir/data/`。

### 手动开发

#### 后端

```bash
# 虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux
# 或 venv/Scripts/activate (Windows)

pip install -r requirements.txt

# 启动服务管理器（自动拉起所有微服务）
python deploy/start_scripts/service_manager.py
```

#### 前端

```bash
cd frontend
bun install
bun run dev      # 开发模式，端口 5173
# 或
bun run build    # 生产构建
```

### Windows 开发注意事项

- 语音功能（pyaudio、Silero VAD、wakeword）在 Windows 上需要额外配置
- 推荐在 Docker 或 WSL2 + PulseAudio 中运行语音网关
- CUPS 打印仅 Linux

## 配置

核心配置在 `.env` 文件，通过环境变量注入：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SINGLETON` | 单机模式(1) / 多机(0) | 1 |
| `BOT_NAME` | AI 名称 | 派蒙 |
| `DEEPSEEK_API_KEY` | LLM API Key | — |
| `DB_PATH` | SQLite 数据库路径 | data/nas_brain.db |
| `WAKEWORD_MODEL` | 唤醒词模型路径 | data/models/xxx.onnx |
| `VAD_TIMEOUT_SEC` | 录音超时 | 10 |
| `VAD_SILENCE_MS` | 静音判定时长 | 1600 |
| `TTS_URL` | TTS 服务地址 | — |
| `HOME_ASSISTANT_URL` | HA 地址 | — |

完整配置参考 `.env` 文件。

## 用户策略

每个用户可独立配置三种策略：

| 策略 | 行为 |
|------|------|
| **smart** | 处理器优先 → LLM + 工具调用 |
| **direct** | 处理器优先 → 兜底回复 |
| **ignore** | 只记录聊天，不处理 |

微信群聊支持 @ 检测，未 @ 的消息自动忽略（可配置）。

消息来源与默认策略：

| 来源 | protocol | 默认策略 |
|------|----------|----------|
| 微信 | WECHAT | 按用户配置 |
| 语音 | VOICE | 强制 smart |
| Web | WEB | smart |

## 添加新微服务

1. 创建 `src/your_service/{app.py, schema/, routes/}`（参考现有服务）
2. 注册到 `deploy/service_config.json` 和 `src/common/utils/config_manager.py`
3. 前端需要时添加 api/types/page/路由/菜单
4. Web 服务添加代理路由

详见 `CLAUDE.md`。

## 插件开发

### 添加工具

```python
from . import BaseTool, registry

class MyTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="工具描述",
            parameters={...},    # JSON Schema
            silent=False,        # True 则不播放前缀文本
            final=True,          # True 则直接返回，不回 LLM
        )

    def execute(self, args: dict) -> dict:
        return {"text": "回复", "files": ["/tmp/file.png"]}

registry.register(MyTool())
```

修改后调用 `POST /api/tools/reload` 热加载。

### 添加处理器

```python
from . import BaseProcessor, registry

class MyProcessor(BaseProcessor):
    @property
    def trigger(self) -> str:
        return "IMAGE"  # TEXT | IMAGE | LINK | FILE

    def handle(self, req, ctx) -> dict | None:
        return {"reply": "处理结果"}

registry.register(MyProcessor())
```

## 语音流程

```
唤醒词触发 → 播"我在呢"
  → VAD 录音（检测静音自动停止）
  → 声纹识别（匹配用户 / 归入未分配）
  → STT（SenseVoiceSmall）
  → brain_services（LLM + 工具）
  → TTS 播放
  → __SKIP__ → 标记唤醒记录为 negative
```

状态互斥规则：播放时不录音、录音时不播放、处理中可打断。

## 三层记忆

| 层级 | 存储 | 说明 |
|------|------|------|
| 短期 | chat_messages（最近 N 分钟） | 完整原始消息 |
| 中期 | chat_summaries 表 | LLM 定期压缩的历史摘要 |
| 长期 | data/memory.md | 全局持久化事实 |

- `short_term_window`（分钟）同时控制短期窗口和中期总结频率
- 总结是增量式的：旧总结 + 新增消息 → 新总结

## 数据库

基于 SQLite，单文件 `data/nas_brain.db`。服务启动时自动建表，无需手动迁移。

主要表：
- `users` — 用户（person/group，支持软删除）
- `user_configs` — 用户策略配置
- `voiceprints` — 声纹嵌入向量（192-dim float32）
- `wakeword_records` — 唤醒历史
- `chat_messages` / `chat_summaries` — 聊天记录
- `kv_store` — 键值存储（阈值等）
