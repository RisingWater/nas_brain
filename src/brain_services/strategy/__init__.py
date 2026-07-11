"""strategy/__init__.py — 导出全局单例"""
from .engine import StrategyEngine
from .chat_recorder import ChatRecorder
from .context_builder import LLMContextBuilder
from .tool_filter import ToolFilter

strategy_engine = StrategyEngine()
chat_recorder = ChatRecorder()
context_builder = LLMContextBuilder()
tool_filter = ToolFilter()
