"""中期记忆总结器 — 后台定时压缩早期聊天记录"""
import json
import time
import logging
import threading
import requests
from src.common.utils import cfg
from src.common.clients.deepseek import DeepSeekAPI

logger = logging.getLogger("brain_services.strategy.summarizer")

_SUMMARY_SYSTEM_PROMPT = (
    "你是一个对话摘要助手。请将以下聊天记录压缩为简洁的总结，"
    "保留重要的事件、决定、用户偏好和关键信息。"
    "用中文，控制在 500 字以内。"
)


class SummaryScheduler:
    """后台线程，定期扫描用户并生成中期记忆总结"""

    def __init__(self):
        self.deepseek = DeepSeekAPI()
        self._running = False
        self._thread: threading.Thread | None = None
        self._interval = 1800  # 默认 30 分钟，会被用户配置覆盖

    def start(self, interval_seconds: int = 1800):
        """启动后台总结线程"""
        if self._running:
            return
        self._interval = interval_seconds
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("中期记忆总结器已启动，间隔=%ds", interval_seconds)

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                self._process_all_users()
            except Exception as e:
                logger.error("总结循环异常: %s", e, exc_info=True)
            time.sleep(self._interval)

    def _get_all_user_ids(self) -> list[str]:
        """获取所有有聊天记录的用户列表"""
        # 从 configs 表取有配置的用户 + 从 chat_messages 取有消息的用户
        seen = set()
        try:
            url = cfg.get_service_url("db_services", "/api/user-configs")
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                for item in items:
                    seen.add(item["user_id"])
        except Exception:
            pass
        # 也扫描有消息但没配置的用户
        # 通过 max-id 端点可以判断是否有用户
        return list(seen)

    def _process_all_users(self):
        """遍历所有用户，检查是否需要总结"""
        # 从 user_configs 获取所有用户
        try:
            # 默认总结所有有配置的用户
            url = cfg.get_service_url("db_services", "/api/user-configs")
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return
            items = resp.json().get("items", [])
        except Exception as e:
            logger.error("获取用户配置列表失败: %s", e)
            return

        for item in items:
            user_id = item["user_id"]
            window = item.get("short_term_window", 30)
            # 总结周期 = short_term_window（比如 30 分钟总结一次已过期的消息）
            # 这里只总结那些 short_term_window 之前的消息
            try:
                self._summarize_user(user_id, window)
            except Exception as e:
                logger.error("用户 %s 总结失败: %s", user_id, e)

    def _summarize_user(self, user_id: str, window_minutes: int):
        """对单个用户执行中期总结"""
        # 1. 查已总结到的最大 msg_id
        try:
            url = cfg.get_service_url("db_services", f"/api/chat-summaries/{user_id}/max-msg-id")
            resp = requests.get(url, timeout=10)
            summarized_max = resp.json().get("max_id", 0) if resp.status_code == 200 else 0
        except Exception:
            summarized_max = 0

        # 2. 查当前最大 msg_id
        try:
            url = cfg.get_service_url("db_services", f"/api/chat-messages/{user_id}/max-id")
            resp = requests.get(url, timeout=10)
            current_max = resp.json().get("max_id", 0) if resp.status_code == 200 else 0
        except Exception:
            return

        # 3. 没有新消息 → 跳过
        if current_max <= summarized_max:
            logger.debug("用户 %s 无新消息，跳过总结", user_id)
            return

        # 4. 获取新消息（已过短期窗口期的，即窗口之前的历史）
        # 读取 summarized_max 之后、窗口时间之前的所有消息
        import datetime
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(minutes=window_minutes))
        try:
            url = cfg.get_service_url("db_services", f"/api/chat-messages/{user_id}")
            resp = requests.get(url, params={
                "since_id": summarized_max,
                "limit": 500,  # 最多拉 500 条用于总结
            }, timeout=15)
            if resp.status_code != 200:
                return
            data = resp.json()
            messages = data.get("messages", [])
        except Exception as e:
            logger.error("获取用户 %s 聊天记录失败: %s", user_id, e)
            return

        # 只总结窗口之前的消息（短期记忆之外的历史）
        old_messages = [m for m in messages if m.get("created_at", "") < cutoff.strftime("%Y-%m-%d %H:%M:%S")]
        if not old_messages:
            logger.debug("用户 %s 窗口内无过期消息，跳过总结", user_id)
            return

        # 5. 调 DeepSeek 压缩
        log_lines = []
        for m in old_messages:
            role = m.get("role", "?")
            content = (m.get("content") or "")[:200]
            tool = m.get("tool_name", "")
            if tool:
                log_lines.append(f"[{role} 调用 {tool}]: {content}")
            else:
                log_lines.append(f"[{role}]: {content}")

        log_text = "\n".join(log_lines)
        if not log_text.strip():
            return

        prompt = f"请总结以下聊天记录：\n\n{log_text}"
        summary = self.deepseek.ask_single_question(prompt, timeout=30)
        if not summary:
            logger.warning("用户 %s 总结生成失败", user_id)
            return

        # 限制总结长度
        summary = summary[:2000]

        # 6. 存入 chat_summaries
        try:
            url = cfg.get_service_url("db_services", "/api/chat-summaries")
            resp = requests.post(url, json={
                "user_id": user_id,
                "summary": summary,
                "last_msg_id": current_max,
            }, timeout=10)
            if resp.status_code == 201:
                logger.info("用户 %s 中期总结完成: %d 条消息 → %d 字",
                            user_id, len(old_messages), len(summary))
        except Exception as e:
            logger.error("保存总结失败: %s", e)


# 全局单例
summarizer = SummaryScheduler()
