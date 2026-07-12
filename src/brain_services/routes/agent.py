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


def _process_async(req: AgentRequest):
    """后台处理：策略引擎处理 → 推送回复到 gateway"""
    try:
        response = strategy_engine.process(req)

        if not response.data:
            return

        who = req.metadata.get("wechat_name", "")

        # 推送文本回复
        text = response.data.get("text", "")
        if text and req.protocol == ProtocolType.WECHAT and who:
            _send_wechat_text(who, text)

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
