"""brain_services — 接收网关请求的路由

处理流程：
1. 收到 AgentRequest
2. 策略引擎判断是否跳过 → 是否 direct/smart
3. processor 优先处理 → LLM + tools（smart 模式）
4. 返回响应，处理附件（图片/文件）
"""
import os
import logging
from fastapi import APIRouter
from ..schema.brain_schema import AgentResponse
from src.common.schemas.agent_request import AgentRequest, ProtocolType
from ..strategy import strategy_engine

logger = logging.getLogger("brain_services")

router = APIRouter()


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


@router.post("", response_model=AgentResponse)
async def receive_request(req: AgentRequest):
    """接收 AgentRequest，由策略引擎分流处理"""
    logger.info("收到请求: id=%s user=%s type=%s content=%.50s",
                req.request_id, req.user_id, req.content_type.value, req.content or "")

    # 交由策略引擎处理
    response = strategy_engine.process(req)

    # 处理附件（工具调用可能产生文件）
    if response.data and response.data.get("text") and req.protocol == ProtocolType.WECHAT:
        files = response.data.get("files", [])
        who = req.metadata.get("wechat_name", "")
        for fp in files:
            if os.path.exists(fp):
                _send_wechat_file(who, fp)
                try:
                    os.remove(fp)
                except Exception:
                    pass

    return response
