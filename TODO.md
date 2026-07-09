# 开发计划

## 阶段 1：TTS 语音合成微服务

- [ ] `src/tts_services/` — FastAPI 微服务，端口 9041
  - [ ] `app.py` — FastAPI 入口，设置 LOG_SERVER_NAME
  - [ ] `tts_engine.py` — TTS 引擎（移植 paimon_assist HttpTTS）
  - [ ] `tts_cache.py` — 语音缓存（文件缓存，避免重复合成）
  - [ ] `routes/tts.py` — API 路由
    - `POST /api/tts/synthesize` — 文本→音频文件返回
    - `POST /api/tts/speak` — 文本→合成并播放（需音频设备）
- [ ] 注册到 `deploy/service_config.json`
- [ ] 添加 `TTS_URL` 到 .env

## 阶段 2：定时任务微服务

- [ ] `src/timer_services/` — FastAPI 微服务，端口 9040
  - [ ] `app.py` — FastAPI 入口 + 后台调度线程（每 30 秒扫到期任务）
  - [ ] `scheduler.py` — 调度引擎
    - 查 `reminders` 表到期未完成的任务
    - smart → POST brain_services/api/agent-request
    - direct+wechat → POST wechat_gateway/api/gateway/send-text
    - direct+voice → POST tts_services/api/tts/speak
    - 执行后标记 done=true
  - [ ] `routes/reminders.py` — CRUD API
    - `GET /api/reminders` — 列表（分页，筛选 done）
    - `POST /api/reminders` — 创建
    - `PUT /api/reminders/{id}` — 编辑
    - `DELETE /api/reminders/{id}` — 删除
- [ ] `db_services` 新增 `reminders` 表
  - schema: id, user_id, content, rtype, rdatetime, lunar, strategy, prompt, notify_type, done, created_at
- [ ] 注册到 `deploy/service_config.json`
- [ ] web_services 代理 `/api/reminders`
- [ ] 前端定时任务管理页面
  - 列表/创建/编辑/删除
  - 策略选择（smart/direct）
  - 通知方式选择（wechat/voice）
  - 农历开关

## 阶段 3：Processor 插件系统

- [ ] `src/brain_services/processors/` — 处理器插件
  - [ ] `__init__.py` — BaseProcessor + ProcessorRegistry
    - `can_handle(content_type: ContentType) → bool`
    - `handle(req: AgentRequest) → dict | None`
    - `priority() → int`
  - [ ] `plugin_manager.py` — 动态加载/热重载
  - [ ] 移植 processor（来自 `D:\wangxu\work\wechat_bot\processor\`）
    - [ ] `chat_processor.py` — 对话处理（简化，无 DeepSeek 依赖）
    - [ ] `homework_processor.py` — 作业 OCR（适配 brain 架构）
    - [ ] 其他按需移植
  - [ ] 管理 API：`GET /api/processors`, `POST /api/processors/reload`
  - [ ] 注册路由到 brain_services
  - [ ] web_services 代理 `/api/processors`

## 阶段 4：Brain Services 策略引擎

- [ ] `src/brain_services/strategy/`
  - [ ] `user_config.py` — 用户策略配置（JSON 或通过 db_services）
    - 每个用户：strategy (smart/direct), tools[], processors[{name, priority}]
  - [ ] `engine.py` — StrategyEngine
    - 判断来源：voice → 强制 smart
    - 判断用户配置 → smart/direct
    - smart → LLM + 用户分配的 tools
    - direct → 用户分配的 processors（按优先级，第一个 can_handle 的 handle）
  - [ ] 管理 API（用户策略 CRUD）
- [ ] 更新 `routes/agent.py` — 改为调用 StrategyEngine
- [ ] 前端用户策略配置页面
  - 选择用户 → 配置策略
  - smart：勾选可用工具
  - direct：勾选处理器 + 设置优先级

## 阶段 5：更新 CLAUDE.md

- [ ] 添加 Processor 插件系统说明
- [ ] 添加策略引擎说明
- [ ] 添加 tts_services / timer_services 端口
- [ ] 添加 wechat_gateway 发送端点说明

## 端口总览

| 服务 | 端口 | 状态 |
|------|------|------|
| service_manager | 9022 | ✅ |
| web_services | 9020 | ✅ |
| db_services | 9021 | ✅ |
| wechat_gateway | 9030 | ✅（收+发）|
| brain_services | 9031 | ✅（工具就绪，策略待开发）|
| timer_services | 9040 | ⏳ |
| tts_services | 9041 | ⏳ |
