"""LLM 处理器 — 函数调用循环"""
import json
import logging
from src.common.clients.deepseek import DeepSeekAPI
from ..tools import registry as tool_registry
from .chat_recorder import ChatRecorder

logger = logging.getLogger("brain_services.strategy.llm_handler")


class LLMHandler:
    """执行 LLM + 工具调用的函数调用循环"""

    MAX_ITERATIONS = 10  # 防止工具调用死循环

    def __init__(self):
        self.deepseek = DeepSeekAPI()
        self.recorder = ChatRecorder()

    def handle(self, user_id: str, messages: list[dict],
               tools: list[dict]) -> tuple[str, list[str]]:
        """函数调用循环：LLM → 工具 → LLM → ... → 最终回复

        Returns:
            (最终回复文本, 附件文件路径列表)
        """
        iteration = 0
        all_files = []

        while iteration < self.MAX_ITERATIONS:
            iteration += 1
            logger.debug("LLM 调用迭代 #%d, 消息数=%d", iteration, len(messages))

            response = self.deepseek.chat_with_tools(messages, tools=tools)
            if not response:
                return "（LLM 响应失败）", all_files

            content = response.get("content") or ""
            tool_calls = response.get("tool_calls")

            if not tool_calls:
                # 没有工具调用 → 最终回复
                self.recorder.record_assistant(user_id, content, tool_calls=None)
                return content, all_files

            # 有工具调用 → 记录 assistant 消息
            self.recorder.record_assistant(user_id, content, tool_calls=tool_calls)
            logger.info("LLM 请求 %d 个工具调用", len(tool_calls))

            # 添加 assistant 消息到上下文
            assistant_msg = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            # 逐个执行工具
            for tc in tool_calls:
                if tc.get("type") != "function":
                    continue
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                try:
                    raw_args = func.get("arguments", "{}")
                    if isinstance(raw_args, str):
                        args = json.loads(raw_args)
                    else:
                        args = raw_args
                except json.JSONDecodeError:
                    args = {}

                logger.info("执行工具: %s args=%s", tool_name, args)
                result = tool_registry.execute(tool_name, args)
                result_text = result.get("text", "（无返回）")
                logger.info("工具 %s 返回: %.100s", tool_name, result_text)

                # 收集附件文件
                files = result.get("files", [])
                if files:
                    all_files.extend(files)

                # 记录工具结果到 DB
                self.recorder.record_tool_result(user_id, tool_name, result)

                # 将工具结果加入上下文
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": json.dumps(result, ensure_ascii=False),
                })

        logger.warning("LLM 工具调用达到最大迭代次数 %d", self.MAX_ITERATIONS)
        return "（工具调用次数过多，请简化问题）", all_files
