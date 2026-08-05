"""网关发送 — 统一封装回复推送（wechat_gateway / voice_gateway）

独立模块：user_processor 与 routes 都要用发送函数，放这里避免循环依赖。
"""
import os
import logging
import requests
from src.common.utils import cfg

logger = logging.getLogger("brain_services.gateway_sender")


def send_wechat_text(who: str, text: str):
    """通过 wechat_gateway 发送文本消息"""
    try:
        url = cfg.get_service_url("wechat_gateway", "/api/gateway/send-text")
        resp = requests.post(url, json={"who": who, "msg": text}, timeout=10)
        if resp.status_code == 200:
            logger.info("回复已发送到 %s: %.50s", who, text)
        else:
            logger.warning("发送回复失败: %s", resp.text)
    except Exception as e:
        logger.error("发送回复异常: %s", e)


def send_wechat_file(who: str, file_path: str) -> bool:
    """通过 wechat_gateway 发送文件到微信"""
    try:
        url = cfg.get_service_url("wechat_gateway", "/api/gateway/send-file")
        with open(file_path, "rb") as f:
            resp = requests.post(
                url,
                data={"who": who, "wxname": ""},
                files={"file": (os.path.basename(file_path), f, "application/octet-stream")},
                timeout=30,
            )
        data = resp.json()
        if data.get("code") == 200:
            logger.info("文件已发送到 %s: %s", who, file_path)
            return True
        logger.warning("发送文件失败: %s", data.get("message"))
    except Exception as e:
        logger.error("发送文件异常: %s", e)
    return False


def update_wakeword_category(wakeword_id: str, category: str):
    """更新唤醒词分类（voice 播放成功/跳过反馈）"""
    try:
        url = cfg.get_service_url("db_services", "/api/wakeword/records")
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            for item in items:
                if item.get("wakeword_id") == wakeword_id:
                    rid = item["id"]
                    url2 = cfg.get_service_url("db_services", f"/api/wakeword/records/{rid}/category")
                    requests.put(url2, json={"category": category}, timeout=5)
                    break
    except Exception as e:
        logger.error("更新唤醒词分类异常: %s", e)


def send_voice_text(text: str, wakeword_id: str = "", request_id: str = ""):
    """通过 voice_gateway 播放语音"""
    if not text or text.strip() == "__SKIP__":
        logger.info("语音 SKIP，不播放")
        if wakeword_id:
            update_wakeword_category(wakeword_id, "negative")
        return
    try:
        url = cfg.get_service_url("voice_gateway", "/api/voice/speak")
        resp = requests.post(url, json={"text": text, "request_id": request_id}, timeout=120)
        if resp.status_code == 200:
            logger.info("语音已播放: %.50s", text)
            if wakeword_id:
                update_wakeword_category(wakeword_id, "positive")
        else:
            logger.warning("语音播放失败: %s", resp.text)
    except Exception as e:
        logger.error("语音播放异常: %s", e)
