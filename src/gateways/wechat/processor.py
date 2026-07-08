"""wechat_gateway 核心 — 消息轮询、用户查找、归一化转发"""
import os
import uuid
import json
import logging
import time
import requests
from datetime import datetime
from typing import Optional

from src.common.clients.wxauto import WXAuto
from src.common.schemas.agent_request import (
    AgentRequest, ProtocolType, ChatType, ContentType,
)
from .routes.status import record_message

logger = logging.getLogger("wechat_gateway")

# db_services 地址
_DB_HOST = os.getenv("DB_SERVICE_HOST", "127.0.0.1")
_DB_PORT = os.getenv("DB_SERVICE_PORT", "9021")
_DB_BASE = f"http://{_DB_HOST}:{_DB_PORT}/api/users"

# brain_services 地址
_BRAIN_HOST = os.getenv("BRAIN_SERVICE_HOST", "127.0.0.1")
_BRAIN_PORT = os.getenv("BRAIN_SERVICE_PORT", "9031")
_BRAIN_URL = f"http://{_BRAIN_HOST}:{_BRAIN_PORT}/api/agent-request"

# 轮询间隔（秒）
_POLL_INTERVAL = int(os.getenv("WECHAT_POLL_INTERVAL", "3"))


class WeChatProcessor:
    """微信消息处理器"""

    def __init__(self):
        self.wxauto = WXAuto()
        self._running = False

    # ---- 用户查找 ----

    def _find_user_by_wechat(self, wechat_name: str) -> Optional[dict]:
        """通过 wechat_name 查找 db_services 中的用户"""
        try:
            resp = requests.get(
                f"{_DB_BASE}/by-wechat",
                params={"wechat_name": wechat_name},
                timeout=5,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                return None
            logger.warning("查找用户意外响应 %s: %s", resp.status_code, resp.text)
            return None
        except requests.RequestException as e:
            logger.error("查找用户失败: %s", e)
            return None

    # ---- 归一化 ----

    def _to_content_type(self, msg_type: str) -> ContentType:
        """将微信消息类型映射为 ContentType"""
        mapping = {
            "text": ContentType.TEXT,
            "image": ContentType.IMAGE,
            "voice": ContentType.VOICE,
            "file": ContentType.FILE,
            "video": ContentType.VIDEO,
            "link": ContentType.LINK,
        }
        return mapping.get(msg_type, ContentType.TEXT)

    def _to_chat_type(self, raw_chat_type: str) -> ChatType:
        """将微信 chat_type 映射为 ChatType"""
        if raw_chat_type == "group":
            return ChatType.GROUP
        return ChatType.PRIVATE

    def _build_agent_request(self, user: dict, msg: dict) -> Optional[AgentRequest]:
        """将单条微信消息归一化为 AgentRequest"""
        msg_type = msg.get("type", "text")
        content_type = self._to_content_type(msg_type)
        raw_chat_type = msg.get("chat_type", "friend")
        chat_name = msg.get("chat_name", "")

        # 根据消息类型提取不同字段
        content = msg.get("content", "")
        file_id = None
        link_url = None
        meta = {
            "wechat_name": chat_name,
            "raw_chat_type": raw_chat_type,
            "message_id": msg.get("id", ""),
        }

        if msg_type == "text":
            content = msg.get("content", "")

        elif msg_type == "image":
            content = msg.get("content", "")
            file_id = msg.get("file_id")
            if msg.get("file_info"):
                meta["file_name"] = msg["file_info"].get("filename")

        elif msg_type == "file":
            content = msg.get("content", "")
            file_id = msg.get("file_id")
            if msg.get("file_info"):
                meta["file_name"] = msg["file_info"].get("filename")

        elif msg_type == "voice":
            # 语音消息用语音转文字结果作为 content
            content = msg.get("voice_to_text") or msg.get("content", "")

        elif msg_type == "link":
            content = msg.get("content", "")
            link_url = msg.get("url")

        return AgentRequest(
            protocol=ProtocolType.WECHAT,
            request_id=f"wx_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now(),
            chat_type=self._to_chat_type(raw_chat_type),
            user_id=user["user_id"],
            content_type=content_type,
            content=content,
            link_url=link_url,
            file_id=file_id,
            metadata=meta,
        )

    # ---- 处理单条消息 ----

    def _process_one(self, msg: dict):
        """处理一条微信消息：查用户 → 归一化 → 发到 brain_services"""
        chat_name = msg.get("chat_name", "")

        # 查用户
        user = self._find_user_by_wechat(chat_name)
        if not user:
            logger.info("丢弃未知用户消息: %s", chat_name)
            return

        # 归一化
        agent_req = self._build_agent_request(user, msg)
        if not agent_req:
            return

        logger.info("转发消息 user=%s type=%s len=%d",
                     user["user_id"], agent_req.content_type.value, len(agent_req.content))

        # 发送到 brain_services
        try:
            resp = requests.post(
                _BRAIN_URL,
                json=agent_req.model_dump(),
                timeout=10,
            )
            if resp.status_code == 200:
                record_message()
            else:
                logger.warning("brain_services 返回 %s: %s", resp.status_code, resp.text)
        except requests.RequestException as e:
            logger.error("发送到 brain_services 失败: %s", e)

    # ---- 轮询循环 ----

    def run_loop(self):
        """消息轮询主循环（同步，在后台线程中运行）"""
        if not self.wxauto.is_valid():
            logger.warning("WXAuto 未配置，跳过消息轮询")
            return

        wxname = os.getenv("WECHAT_GATEWAY_WXNAME", "")
        if not wxname:
            logger.warning("WECHAT_GATEWAY_WXNAME 未设置，跳过消息轮询")
            return

        self._running = True
        logger.info("开始微信消息轮询 (wxname=%s)", wxname)

        while self._running:
            try:
                # get_next_new_message 内部有 30 秒 HTTP 超时做长轮询
                result = self.wxauto.get_next_new_message()

                if not result.get("success"):
                    logger.warning("获取消息失败: %s", result.get("error"))
                elif result.get("has_message"):
                    messages = result.get("messages", [])
                    logger.info("收到 %d 条消息", len(messages))

                    for msg in messages:
                        # 跳过自己发出的消息
                        if msg.get("attr") == "self":
                            continue
                        self._process_one(msg)

            except Exception as e:
                logger.error("轮询异常: %s", e)

            time.sleep(_POLL_INTERVAL)

        logger.info("消息轮询已停止")

    def stop_loop(self):
        """停止轮询"""
        self._running = False
