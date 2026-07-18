"""LLM 上下文构建器 — 组装三层记忆 + system prompt"""
import os
import json
import logging
import requests
from src.common.utils import cfg

logger = logging.getLogger("brain_services.strategy.context_builder")

_MEMORY_FILE = os.getenv("MEMORY_FILE", "data/memory.md")
_BOT_NAME = os.getenv("BOT_NAME", "NAS Brain")
_DEFAULT_SYSTEM_PROMPT = f"你是 {_BOT_NAME}，一个智能助手。请用中文回答用户的问题。"


def _read_long_term_memory() -> str:
    """读取长期记忆（memory.md）"""
    if not os.path.exists(_MEMORY_FILE):
        return ""
    try:
        with open(_MEMORY_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logger.error("读取长期记忆失败: %s", e)
        return ""


class LLMContextBuilder:
    """按时间段构建 LLM 上下文：system + 长期 + 中期 + 短期 + 当前消息"""

    def build(self, user_id: str, config: dict, current_msg: str,
              protocol: str = "wechat", chat_type: str = "private",
              exclude_msg_id: int | None = None,
              sender: str = "") -> list[dict]:
        """构建 OpenAI-format messages 列表"""
        messages = []

        # 1. System prompt
        system_prompt = (config.get("system_prompt", "") or "").strip()
        if not system_prompt:
            system_prompt = _DEFAULT_SYSTEM_PROMPT
        messages.append({"role": "system", "content": system_prompt})

        # 当前日期
        from datetime import datetime
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        now = datetime.now()
        date_str = now.strftime(f"%Y年%m月%d日 {weekdays[now.weekday()]}")
        messages.append({"role": "system", "content": f"今天是 {date_str}。"})

        # 1b. 来源上下文
        ctx_parts = []
        if protocol == "wechat":
            if chat_type == "group":
                ctx_parts.append("你现在在微信群聊中，用户可能 @ 了你。")
            else:
                ctx_parts.append("你现在在微信私聊中。")
            ctx_parts.append(
                "规则：\n"
                "0. 必须用中文回答\n"
                "1. 禁止使用markdown格式\n"
            )
        elif protocol == "voice":
            ctx_parts.append(
                "你正在通过语音与用户对话，回复会通过语音播放。\n"
                "规则：\n"
                "0. 判断用户输入是否值得回复。以下情况直接回复 __SKIP__（只回复这三个词）：\n"
                "   - 单个字、语气词（嗯、啊、哦、哈、唉）\n"
                "   - 自言自语、不是对你说的对话\n"
                "   - 语法不通、乱码、语音识别错误导致的无意义文本\n"
                "1. 不要使用任何emoji、颜文字、特殊符号\n"
                "2. 不要使用markdown格式\n"
                "3. 用中文回答，语气活泼可爱\n"
                "4. 回复尽量简短在1-2句话内\n"
                "5. 使用口语化的表达方式\n"
                "6. 数字用中文写（二十五而不是25），语音模型无法念阿拉伯数字"
            )
        if ctx_parts:
            messages.append({"role": "system", "content": " ".join(ctx_parts)})

        # 2. Long-term memory (memory.md)
        long_term = _read_long_term_memory()
        if long_term:
            messages.append({
                "role": "system",
                "content": f"【长期记忆】\n{long_term}\n（以上是长期记忆，由你维护的事实列表）",
            })

        # 3. Mid-term memory (chat_summaries)
        mid_term = self._get_mid_term_summary(user_id)
        if mid_term:
            messages.append({
                "role": "system",
                "content": f"【历史对话总结】\n{mid_term}",
            })

        # 4. Short-term memory (recent chat_messages)
        window_minutes = config.get("short_term_window", 30)
        short_term = self._get_short_term_history(user_id, window_minutes, exclude_msg_id)
        for msg in short_term:
            messages.append(msg)

        # 5. Current user message
        msg_content = current_msg
        if sender and chat_type == "group":
            msg_content = f"{sender}: {current_msg}"
        messages.append({"role": "user", "content": msg_content})

        return messages

    def _get_mid_term_summary(self, user_id: str) -> str | None:
        """获取中期记忆总结"""
        try:
            url = cfg.get_service_url("db_services", f"/api/chat-summaries/{user_id}/latest")
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("summary")
        except Exception:
            pass
        return None

    def _get_short_term_history(self, user_id: str, window_minutes: int,
                                 exclude_id: int | None = None) -> list[dict]:
        """获取短期记忆（最近 N 分钟内的消息），可选排除某条 ID"""
        try:
            url = cfg.get_service_url("db_services", f"/api/chat-messages/{user_id}")
            import datetime
            since = (datetime.datetime.utcnow() - datetime.timedelta(minutes=window_minutes))
            resp = requests.get(url, params={
                "limit": 200,
                "since_time": since.strftime("%Y-%m-%d %H:%M:%S"),
            }, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                logger.info("短期记忆: since_time=%s, total=%d, 消息IDs=%s",
                             since.strftime("%Y-%m-%d %H:%M:%S"),
                             data.get("total"),
                             [m.get("id") for m in data.get("messages", [])])
                result = []
                for msg in data.get("messages", []):
                    if exclude_id is not None and msg.get("id") == exclude_id:
                        continue
                    role = msg.get("role", "")
                    if role in ("user", "assistant"):
                        content = msg.get("content") or ""
                        # 群聊消息中附带发送者名字
                        msg_meta = msg.get("metadata", {})
                        if isinstance(msg_meta, str):
                            try:
                                msg_meta = json.loads(msg_meta)
                            except Exception:
                                msg_meta = {}
                        sender = msg_meta.get("sender", "") if isinstance(msg_meta, dict) else ""
                        if sender and role == "user":
                            content = f"{sender}: {content}"
                        entry = {
                            "role": role,
                            "content": content,
                        }
                        # 恢复 tool_calls（存储在 DB 的 tool_calls 字段）
                        tc = msg.get("tool_calls")
                        if tc:
                            entry["tool_calls"] = tc
                        result.append(entry)
                    elif role == "tool":
                        # 从 metadata 中恢复原始 tool_call_id
                        meta = msg.get("metadata", {})
                        if isinstance(meta, str):
                            try:
                                meta = json.loads(meta)
                            except Exception:
                                meta = {}
                        tc_id = meta.get("tool_call_id", "") if isinstance(meta, dict) else ""
                        tool_name = msg.get("tool_name") or ""
                        tool_result = msg.get("tool_result") or {}
                        result.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": json.dumps(tool_result, ensure_ascii=False),
                        })
                    elif role == "processor":
                        result.append({
                            "role": "assistant",
                            "content": f"[处理器 {msg.get('processor_name')}]: {msg.get('content')}",
                        })

                # 修复缺失 tool_call_id 的 tool 消息：按顺序匹配前一条 assistant 的 tool_calls
                tc_idx_map = {}  # 记录每个 assistant 消息后第几个 tool
                for i, entry in enumerate(result):
                    if entry.get("tool_calls"):
                        tc_idx_map[i] = 0  # 从这个位置开始计数 tool
                    elif entry.get("role") == "tool" and not entry.get("tool_call_id"):
                        # 找到前面最近的 assistant 并依次分配 tool_call_id
                        for j in range(i - 1, -1, -1):
                            if result[j].get("tool_calls"):
                                tc_list = result[j]["tool_calls"]
                                idx = tc_idx_map.get(j, 0)
                                if idx < len(tc_list):
                                    entry["tool_call_id"] = tc_list[idx]["id"]
                                    tc_idx_map[j] = idx + 1
                                break
                return result
        except Exception as e:
            logger.error("获取短期记忆失败: %s", e)
        return []
