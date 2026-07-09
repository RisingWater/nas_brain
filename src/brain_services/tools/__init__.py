"""brain_services 工具插件系统 — BaseTool + ToolRegistry"""
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger("brain_services.tools")


class BaseTool:
    """工具基类。子类需实现 execute(args) → str。"""

    def __init__(self, name: str, description: str, parameters: dict,
                 silent: bool = False, final: bool = False):
        self.name = name
        self.description = description
        self.silent = silent
        self.final = final
        self._schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }

    @property
    def schema(self) -> dict:
        return self._schema

    def execute(self, args: dict) -> dict:
        """执行工具，返回 {"text": "回复文字", "files": ["/path/to/file", ...]}

        - text: 必填，回复给用户的文字
        - files: 可选，临时文件路径列表（由 agent route 发送后清理）
        """
        raise NotImplementedError

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "silent": self.silent,
            "final": self.final,
            "parameters": self._schema["function"]["parameters"],
        }


class ToolRegistry:
    """工具注册表（单例）"""

    _instance: Optional["ToolRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool
        logger.info("注册工具: %s", tool.name)

    def unregister(self, name: str):
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def get_all(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_schemas(self) -> list[dict]:
        return [t.schema for t in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> dict:
        """执行工具，返回 {"text": str, "files": list[str]}

        兼容旧格式：如果工具返回 str，自动包装为 dict。
        """
        tool = self._tools.get(name)
        if not tool:
            return {"text": f"未知工具: {name}", "files": []}
        try:
            result = tool.execute(arguments)
            if isinstance(result, str):
                return {"text": result, "files": []}
            if isinstance(result, dict):
                return result
            return {"text": str(result), "files": []}
        except Exception as e:
            logger.exception("工具 %s 执行失败", name)
            return {"text": f"工具调用失败: {e}", "files": []}

    def clear(self):
        self._tools.clear()

    def to_list(self) -> list[dict]:
        return [t.to_dict() for t in self._tools.values()]


# 全局单例
registry = ToolRegistry()
