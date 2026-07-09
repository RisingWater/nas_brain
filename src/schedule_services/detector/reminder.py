"""reminder_detector — 标准定时提醒调度器（从 db_services 加载 schedules 到内存）"""
import logging
import time
from datetime import datetime
from typing import Optional

from ..db_client import db_client
from .base import BaseDetector, DetectorContext, registry

logger = logging.getLogger("schedule_services.detector.reminder")

_TYPE_CN = {"once": "一次性", "daily": "每天", "monthly": "每月"}


class ReminderDetector(BaseDetector):
    """标准定时提醒调度器

    启动时全量拉取 schedules 到内存，每次 process_loop 检查到期任务。
    API 增删改后调用 reload() 同步缓存。
    """

    name = "reminder"
    interval = 60  # 每分钟检查一次
    visible = False  # 内置调度器，不在管理页面显示

    def __init__(self):
        super().__init__()
        self._schedules: list[dict] = []
        self._last_reload = 0.0

    def reload(self):
        """从 db_services 全量刷新缓存（启动时 + API 增删改后调用）"""
        try:
            self._schedules = db_client.list_all(done=False)
            self._last_reload = time.time()
            logger.info("Reminder 缓存刷新: %d 条待执行", len(self._schedules))
        except Exception as e:
            logger.error("Reminder 缓存刷新失败: %s", e)

    def get_cache(self) -> list[dict]:
        """获取内存缓存（供 API 查询使用）"""
        return self._schedules

    def get_cache_by_id(self, schedule_id: int) -> Optional[dict]:
        for s in self._schedules:
            if s["id"] == schedule_id and not s.get("done"):
                return s
        return None

    def process_loop(self, ctx: DetectorContext):
        """每分钟检查到期任务"""
        now = datetime.now()

        for s in self._schedules[:]:  # 遍历副本
            if s.get("done"):
                continue
            if self._is_due(s, now):
                logger.info("触发提醒 #%d: %s", s["id"], s["content"])
                self._dispatch(s, ctx)

                if s["rtype"] == "once":
                    s["done"] = True
                    try:
                        db_client.mark_done(s["id"])
                    except Exception as e:
                        logger.error("标记完成失败 #%d: %s", s["id"], e)

    def _is_due(self, s: dict, now: datetime) -> bool:
        """判断任务是否到期"""
        rtype = s.get("rtype", "once")
        rdatetime = s.get("rdatetime", "")

        if not rdatetime:
            return False

        current_minutes = now.hour * 60 + now.minute

        if rtype == "once":
            # rdatetime = "2026-07-09 21:00"
            try:
                task_time = datetime.strptime(rdatetime, "%Y-%m-%d %H:%M")
                return now >= task_time and abs((now - task_time).total_seconds()) < 120
            except ValueError:
                return False

        elif rtype == "daily":
            # rdatetime = "21:00"
            try:
                parts = rdatetime.strip().split(":")
                task_minutes = int(parts[0]) * 60 + int(parts[1])
                return current_minutes == task_minutes
            except (ValueError, IndexError):
                return False

        elif rtype == "monthly":
            # rdatetime = "15 21:00"
            try:
                parts = rdatetime.strip().split(" ")
                day = int(parts[0])
                time_parts = parts[1].split(":")
                if now.day != day:
                    return False
                task_minutes = int(time_parts[0]) * 60 + int(time_parts[1])
                return current_minutes == task_minutes
            except (ValueError, IndexError):
                return False

        return False

    def _dispatch(self, s: dict, ctx: DetectorContext):
        """按策略分发任务"""
        strategy = s.get("strategy", "direct")
        notify_type = s.get("notify_type", "wechat")
        content = s.get("content", "")
        user_id = s.get("creator_id", s.get("user_id", ""))
        notify_target = s.get("notify_target", "") or ""

        if strategy == "smart":
            self._dispatch_smart(s)
        else:
            if notify_type == "wechat":
                # notify_target 优先，空则查创建者的微信名
                who = notify_target or self._resolve_wechat_name(user_id) or user_id
                ctx.send_wechat(who=who, msg=f"🔔 {content}")
            elif notify_type == "voice":
                ctx.speak_voice(text=content)

    def _resolve_wechat_name(self, user_id: str) -> str | None:
        """通过 user_id 查用户的 wechat_name"""
        try:
            import requests
            from src.common.utils import cfg
            url = cfg.get_service_url("db_services", f"/api/users/{user_id}")
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json().get("wechat_name")
        except Exception as e:
            logger.error("查询用户 %s 微信名失败: %s", user_id, e)
        return None

    def _dispatch_smart(self, s: dict):
        """smart 策略 — POST brain_services"""
        try:
            import requests
            from src.common.utils import cfg

            prompt = s.get("prompt") or s.get("content", "")
            url = cfg.get_service_url("brain_services", "/api/agent-request")

            from src.common.schemas.agent_request import (
                AgentRequest, ProtocolType, ChatType, ContentType,
            )
            from datetime import datetime
            import uuid

            req = AgentRequest(
                protocol=ProtocolType.WEB,
                request_id=f"sched_{uuid.uuid4().hex[:12]}",
                timestamp=datetime.now(),
                chat_type=ChatType.PRIVATE,
                user_id=s.get("creator_id", s.get("user_id", "")),
                content_type=ContentType.TEXT,
                content=prompt,
            )
            resp = requests.post(url, json=req.model_dump(), timeout=15)
            if resp.status_code != 200:
                logger.warning("brain_services 返回 %s", resp.status_code)
        except Exception as e:
            logger.error("Smart 调度失败 #%d: %s", s["id"], e)


# 模块级注册 — 导入即注册到全局 registry
registry.register(ReminderDetector())
