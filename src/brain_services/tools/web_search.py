"""网络搜索工具 — 通过 Claude CLI 搜索"""
import os
import subprocess
import logging
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.web_search")


class WebSearchTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="web_search",
            display_name="搜索网页",
            description="仅用于查询最新时效性信息：新闻、实时数据、近期事件。常识、历史、科学、编程等知识类问题不要调用。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或问题，用中文"},
                },
                "required": ["query"],
            },
        )

    def execute(self, args: dict) -> dict:
        query = args.get("query", "").strip()
        if not query:
            return {"text": "搜索失败：查询内容为空"}

        claude_bin = os.getenv("CLAUDE_BIN", "claude")
        prompt = f"请搜索网络获取以下信息，并给出简洁的总结：{query}"
        try:
            result = subprocess.run(
                [claude_bin, "-p", prompt, "--output-format", "text",
                 "--allowedTools", "WebSearch,WebFetch",
                 "--permission-mode", "bypassPermissions"],
                capture_output=True, text=True, encoding="utf-8",
                timeout=120,
            )
            output = (result.stdout or "").strip()
            if not output and result.stderr:
                return {"text": f"搜索失败：{(result.stderr or '')[:300]}"}
            return {"text": output or "搜索未返回结果"}
        except subprocess.TimeoutExpired:
            return {"text": "搜索超时，请稍后重试"}
        except FileNotFoundError:
            return {"text": "搜索失败：找不到 claude CLI，请确认已安装 Claude Code"}
        except Exception as e:
            return {"text": f"搜索失败：{e}"}


registry.register(WebSearchTool())
