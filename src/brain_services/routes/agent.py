"""brain_services — 接收网关请求的路由

处理流程：
1. 收到 AgentRequest
2. 遍历 processors（按 priority），第一个 can_handle 的执行 handle
3. 无 processor 处理 → 走 LLM + tools（TODO 后续实现）
4. 返回响应，处理附件（图片/文件）
"""
import os
import logging
from fastapi import APIRouter
from ..schema.brain_schema import AgentResponse
from src.common.schemas.agent_request import AgentRequest, ProtocolType
from ..tools import registry as tool_registry
from ..processors import registry as proc_registry

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
    """接收 AgentRequest，按 processor → LLM+tools 顺序处理"""
    logger.info("收到请求: id=%s user=%s type=%s content=%.50s",
                req.request_id, req.user_id, req.content_type.value, req.content or "")

    # 1. 先尝试 processors
    processor, ctx = proc_registry.find_handler(req)
    if processor:
        logger.info("Processor %s 处理请求", processor.name)
        try:
            result = processor.handle(req, ctx)
            if result and "reply" in result:
                return AgentResponse(data={
                    "request_id": req.request_id,
                    "text": result["reply"],
                    "processor": processor.name,
                })
        except Exception as e:
            logger.error("Processor %s 异常: %s", processor.name, e, exc_info=True)

    # 2. TODO: 走 LLM + tools（smart 模式）

    # 3. 默认回复
    return AgentResponse(data={
        "request_id": req.request_id,
        "text": f"已收到你的消息：{req.content or ''}",
        "received": True,
    })
