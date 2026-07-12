"""网页抓取工具 — 通过 Claude CLI 获取 URL 内容"""
import os
import subprocess
import logging
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.web_fetch")


class WebFetchTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="web_fetch",
            description="获取指定 URL 的网页内容并总结。适用于查看文章、文档、公告等在线内容。注意：仅用于获取已知 URL，不要用于搜索。",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要获取的网页 URL，必须以 http:// 或 https:// 开头",
                    },
                },
                "required": ["url"],
            },
        )

    def execute(self, args: dict) -> dict:
        url = args.get("url", "").strip()
        if not url:
            return {"text": "请提供 URL", "files": []}
        if not url.startswith(("http://", "https://")):
            return {"text": "URL 格式错误，必须以 http:// 或 https:// 开头", "files": []}

        claude_bin = os.getenv("CLAUDE_BIN", "claude")
        prompt = f"请获取以下网页的内容并给出简洁的总结：{url}"
        try:
            result = subprocess.run(
                [claude_bin, "-p", prompt, "--output-format", "text",
                 "--allowedTools", "WebFetch",
                 "--permission-mode", "bypassPermissions"],
                capture_output=True, text=True, encoding="utf-8",
                timeout=120,
            )
            output = (result.stdout or "").strip()
            if not output and result.stderr:
                return {"text": f"获取失败：{(result.stderr or '')[:300]}", "files": []}
            return {"text": output or "未获取到内容", "files": []}
        except subprocess.TimeoutExpired:
            return {"text": "获取超时，请稍后重试", "files": []}
        except FileNotFoundError:
            return {"text": "找不到 claude CLI，请确认已安装 Claude Code", "files": []}
        except Exception as e:
            return {"text": f"获取失败：{e}", "files": []}


registry.register(WebFetchTool())
