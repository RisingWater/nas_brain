"""wechat_gateway — 文件下载代理（透传 wxauto 的文件下载接口）"""
import os
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.common.clients.wxauto import WXAuto

logger = logging.getLogger("wechat_gateway")

router = APIRouter()

_wx_client = WXAuto()


@router.get("/files/{file_id}/download")
async def download_file(file_id: str):
    """透传文件下载请求到 wxauto 外部服务"""
    if not _wx_client.is_valid():
        raise HTTPException(503, "WXAuto 未配置")

    api_url = os.getenv("WXAUTO_API_URL", "")
    token = os.getenv("WXAUTO_API_TOKEN", "")
    url = f"{api_url}/api/v1/files/{file_id}/download"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        import requests
        resp = requests.get(url, headers=headers, stream=True, timeout=30)
        resp.raise_for_status()
        return StreamingResponse(
            resp.iter_content(chunk_size=8192),
            media_type=resp.headers.get("content-type", "application/octet-stream"),
        )
    except requests.RequestException as e:
        logger.error("文件下载失败 file_id=%s: %s", file_id, e)
        raise HTTPException(502, f"文件下载失败: {e}")
