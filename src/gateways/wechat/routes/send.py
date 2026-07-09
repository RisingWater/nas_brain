"""wechat_gateway — 微信消息发送端点（供 timer_services 等内部服务调用）"""
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from src.common.clients.wxauto import WXAuto

logger = logging.getLogger("wechat_gateway")

router = APIRouter()

_wx_client = WXAuto()


class SendTextRequest(BaseModel):
    who: str = Field(..., min_length=1, description="接收人微信名/群名")
    msg: str = Field(..., min_length=1, description="消息内容，支持 emoji")
    wxname: str = Field("", description="发消息的微信账号")


@router.post("/send-text")
async def send_text(req: SendTextRequest):
    """发送微信文本消息"""
    if not _wx_client.is_valid():
        raise HTTPException(503, "WXAuto 未配置")
    try:
        result = _wx_client.send_text_message(who=req.who, msg=req.msg, wxname=req.wxname)
        if result.get("success"):
            logger.info("文本已发送 -> %s: %.30s", req.who, req.msg)
            return {"code": 200, "data": result.get("data"), "message": "发送成功"}
        raise HTTPException(502, f"发送失败: {result.get('error')}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"发送异常: {e}")


@router.post("/send-file")
async def send_file(
    who: str = Form(..., min_length=1),
    wxname: str = Form(""),
    file: UploadFile = File(..., description="要发送的文件"),
):
    """上传文件并通过微信发送（不落地，直接转发到 wxauto）"""
    if not _wx_client.is_valid():
        raise HTTPException(503, "WXAuto 未配置")
    try:
        content = await file.read()
        result = _wx_client.send_file_data(
            who=who, filename=file.filename or "file", data=content, wxname=wxname,
        )
        if result.get("success"):
            logger.info("文件已发送 -> %s: %s", who, file.filename)
            return {"code": 200, "data": result.get("data"), "message": "发送成功"}
        raise HTTPException(502, f"发送失败: {result.get('error')}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"发送异常: {e}")
