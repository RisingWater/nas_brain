"""工具过滤器 — 根据 allowed_tools 白名单过滤"""
import logging

logger = logging.getLogger("brain_services.strategy.tool_filter")


class ToolFilter:
    """根据用户配置的 allowed_tools 白名单过滤工具列表"""

    def filter(self, all_schemas: list[dict],
               allowed_tools: list[str] | None) -> list[dict]:
        """过滤工具 schema 列表

        Args:
            all_schemas: 全部工具 schema（OpenAI function-calling 格式）
            allowed_tools: None=全部工具，[]=无工具，["a","b"]=仅指定工具

        Returns:
            过滤后的 schema 列表
        """
        if allowed_tools is None:
            return all_schemas

        allowed_set = set(allowed_tools)
        if not allowed_set:
            return []

        filtered = []
        for schema in all_schemas:
            name = schema.get("function", {}).get("name", "")
            if name in allowed_set:
                filtered.append(schema)

        return filtered
