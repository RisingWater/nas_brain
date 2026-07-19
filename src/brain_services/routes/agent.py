"""brain_services — 接收网关请求的路由

流程：
1. 收到 AgentRequest → 立即返回 200（"已收到"）
2. 后台线程异步处理（processor → LLM + tools）
3. 处理完成后推送回复到 wechat_gateway
"""
import os
import logging
import threading
from fastapi import APIRouter, BackgroundTasks
from ..schema.brain_schema import AgentResponse
from src.common.schemas.agent_request import AgentRequest, ProtocolType
from ..strategy import strategy_engine
from ..stats import stats
from src.common.utils.tracer import trace_event, trace_reply as _trace_reply

logger = logging.getLogger("brain_services")

router = APIRouter()


def _send_wechat_text(who: str, text: str):
    """通过 wechat_gateway 发送文本消息"""
    import requests as _req
    from src.common.utils import cfg
    try:
        url = cfg.get_service_url("wechat_gateway", "/api/gateway/send-text")
        resp = _req.post(url, json={"who": who, "msg": text}, timeout=10)
        if resp.status_code == 200:
            logger.info("回复已发送到 %s: %.50s", who, text)
        else:
            logger.warning("发送回复失败: %s", resp.text)
    except Exception as e:
        logger.error("发送回复异常: %s", e)


def _send_wechat_file(who: str, file_path: str) -> bool:
    """通过 wechat_gateway 发送文件到微信"""
    import requests as _req
    from src.common.utils import cfg
    url = cfg.get_service_url("wechat_gateway", "/api/gateway/send-file")
    try:
        with open(file_path, "rb") as f:
            resp = _req.post(
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


def _send_voice_text(text: str, wakeword_id: str = "", request_id: str = ""):
    """通过 voice_gateway 播放语音"""
    if not text or text.strip() == "__SKIP__":
        logger.info("语音 SKIP，不播放")
        if wakeword_id:
            try:
                _update_wakeword_category(wakeword_id, "negative")
            except Exception:
                pass
        return
    import requests as _req
    from src.common.utils import cfg
    try:
        url = cfg.get_service_url("voice_gateway", "/api/voice/speak")
        resp = _req.post(url, json={"text": text, "request_id": request_id}, timeout=120)
        if resp.status_code == 200:
            logger.info("语音已播放: %.50s", text)
            if wakeword_id:
                try:
                    _update_wakeword_category(wakeword_id, "positive")
                except Exception:
                    pass
        else:
            logger.warning("语音播放失败: %s", resp.text)
    except Exception as e:
        logger.error("语音播放异常: %s", e)


def _update_wakeword_category(wakeword_id: str, category: str):
    """更新唤醒词分类"""
    import requests as _req
    from src.common.utils import cfg
    url = cfg.get_service_url("db_services", "/api/wakeword/records")
    resp = _req.get(url, timeout=10)
    if resp.status_code == 200:
        items = resp.json().get("items", [])
        for item in items:
            if item.get("wakeword_id") == wakeword_id:
                rid = item["id"]
                url2 = cfg.get_service_url("db_services", f"/api/wakeword/records/{rid}/category")
                _req.put(url2, json={"category": category}, timeout=5)
                break


def _process_async(req: AgentRequest):
    """后台处理：策略引擎处理 → 推送回复到 gateway"""
    try:
        response = strategy_engine.process(req)

        if not response.data:
            # 跳过（群聊无 @）或 ignore，不追踪
            return

        # 追踪：实际开始处理
        trace_event(req.request_id, "brain_receive", protocol=req.protocol.value, user_id=req.user_id)

        # 统计 + 追踪
        text = (response.data or {}).get("text", "")
        is_skip = text and text.strip() == "__SKIP__"
        stats.record_request(answered=not is_skip)

        if not is_skip:
            token_meta = {
                "prompt_tokens": req.metadata.get("prompt_tokens", 0),
                "completion_tokens": req.metadata.get("completion_tokens", 0),
            }
            trace_event(req.request_id, "brain_done", protocol=req.protocol.value,
                        user_id=req.user_id, metadata=token_meta)
            if text:
                _trace_reply(req.request_id, reply=text)
        else:
            # __SKIP__：标记但不保留追踪记录
            _trace_reply(req.request_id, skip=True)

        who = req.metadata.get("wechat_name", "")

        # 推送文本回复
        text = response.data.get("text", "")
        if text and req.protocol == ProtocolType.WECHAT and who:
            _send_wechat_text(who, text)
        elif text and req.protocol == ProtocolType.VOICE:
            wakeword_id = (req.metadata or {}).get("wakeword_id", "")
            _send_voice_text(text, wakeword_id, req.request_id)

        # 推送附件文件
        files = response.data.get("files", [])
        if files and who:
            for fp in files:
                if os.path.exists(fp):
                    _send_wechat_file(who, fp)
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
    except Exception as e:
        logger.error("异步处理异常: %s", e, exc_info=True)


@router.post("", response_model=AgentResponse)
async def receive_request(req: AgentRequest):
    """接收 AgentRequest，立即返回，后台异步处理"""
    logger.info("收到请求: id=%s user=%s type=%s content=%.50s",
                req.request_id, req.user_id, req.content_type.value, req.content or "")

    # 起后台线程处理，不阻塞 HTTP 响应
    threading.Thread(target=_process_async, args=(req,), daemon=True).start()

    # 立即返回"已收到"
    return AgentResponse(data={
        "request_id": req.request_id,
        "text": "收到",
        "received": True,
    })


@router.get("/stats")
def get_stats():
    """返回统计信息"""
    return stats.get_stats()
