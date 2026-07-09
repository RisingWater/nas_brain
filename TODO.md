# 开发计划

## 阶段 1：音频播放微服务 ✅

- [x] `src/playback_services/` — FastAPI 微服务，端口 9041
  - [x] `tts_engine.py` — TTS 合成引擎
  - [x] `tts_cache.py` — 文件缓存 + JSON 索引
  - [x] `audio_manager.py` — 播放管理器（队列 + 后台线程）
  - [x] `POST /api/speak/synthesize` — 合成并返回音频
  - [x] `POST /api/speak/play` — 合成并播放（sync/async）
  - [x] `routes/cache.py` — TTS 缓存管理 API
- [x] 前端 TTS 缓存管理页面

## 阶段 2：定时任务微服务 ✅

- [x] `src/schedule_services/` — FastAPI 微服务，端口 9040
  - [x] 调度引擎（每 60 秒遍历所有 detector）
  - [x] DetectorRegistry + 热加载（同 tool 模式）
  - [x] `detector/reminder.py` — 标准定时提醒调度器（内存缓存 + 到期分发）
  - [x] `detector/dsm_loop.py` — 开门检测插件
  - [x] `detector/exam_loop.py` — 考试成绩检测插件
  - [x] `detector/battery_loop.py` — 电量检测插件
  - [x] 全量内存缓存 + CRUD 实时同步
  - [x] 支持指定接收人（notify_target）
  - [x] 分发：smart→brain / direct+wechat→wechat_gateway / direct+voice→playback
- [x] `db_services` schedules 表 CRUD
- [x] `db_services` kv_store 表（持久化 detector 去重状态）
- [x] `src/common/clients/` 共享客户端库
- [x] 前端：定时提醒管理 + 定时任务(Detector)管理页面
- [x] brain_services reminder/location tool 迁移到新架构

## 阶段 3：Processor 插件系统 ✅

- [x] `src/brain_services/processors/` — 处理器插件
  - [x] BaseProcessor + ProcessorRegistry + ProcessorContext
  - [x] plugin_manager 动态加载/热重载
  - [x] 移植 3 个处理器：homework(OCR) / print(CUPS) / urlsave(链接保存)
- [x] 管理 API + web_services 代理
- [x] 前端处理器管理页面（列表 + 热重载）
- [x] `src/common/lib/` — 工具库移植
  - [x] file_converter, image_binarize, file_recognize
  - [x] printer(CUPS), fixed_web_converter
- [x] `src/common/clients/` — deepseek / baidu_ocr
- [x] agent.py 集成 processor 优先处理

## 阶段 4：Brain Services 策略引擎 ⏳

- [ ] `src/brain_services/strategy/`
  - [ ] 用户策略配置（smart/direct）
  - [ ] StrategyEngine — 来源判断 + 策略路由
  - [ ] 管理 API + 前端配置页面
  - [ ] 更新 `routes/agent.py` 调用 StrategyEngine

## 阶段 5：更新 CLAUDE.md ⏳

- [ ] 添加 Processor 插件系统说明
- [ ] 添加策略引擎说明
- [ ] 添加 schedule_services / playback_services 端口说明
- [ ] 添加公共客户端库 / 工具库说明
- [ ] 添加服务发现（SINGLETON）说明
- [ ] 添加 Tool 返回值格式说明

## 端口总览

| 服务 | 端口 | 状态 |
|------|------|------|
| service_manager | 9022 | ✅ |
| web_services | 9020 | ✅ |
| db_services | 9021 | ✅ |
| wechat_gateway | 9030 | ✅（收+发）|
| brain_services | 9031 | ✅（工具+处理器就绪，策略待开发）|
| schedule_services | 9040 | ✅ |
| playback_services | 9041 | ✅ |
