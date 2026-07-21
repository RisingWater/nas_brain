"""LLM 处理器 — 函数调用循环"""
import json
import os
import logging
from src.common.clients.deepseek import DeepSeekAPI
from ..tools import registry as tool_registry
from .chat_recorder import ChatRecorder
from ..stats import stats
from ..status import ai_status
from src.common.utils.tracer import trace_event as _trace_event

logger = logging.getLogger("brain_services.strategy.llm_handler")

_DUMP = os.getenv("BRAIN_SERVICE_DUMP_MSG")


class LLMHandler:
    """执行 LLM + 工具调用的函数调用循环"""

    MAX_ITERATIONS = 10  # 防止工具调用死循环

    def __init__(self):
        self.deepseek = DeepSeekAPI()
        self.recorder = ChatRecorder()

    def handle(self, user_id: str, messages: list[dict],
               tools: list[dict], request_id: str = "") -> tuple[str, list[str], dict]:
        """函数调用循环：LLM → 工具 → LLM → ... → 最终回复

        Returns:
            (最终回复文本, 附件文件路径列表, {prompt_tokens, completion_tokens})
        """
        iteration = 0
        all_files = []
        is_first_llm = True
        req_prompt = 0
        req_completion = 0

        while iteration < self.MAX_ITERATIONS:
            iteration += 1
            logger.debug("LLM 调用迭代 #%d, 消息数=%d", iteration, len(messages))

            if _DUMP:
                logger.info("LLM REQ: %s",
                    json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False, default=str))
            response = self.deepseek.chat_with_tools(messages, tools=tools)
            # 记录 token 用量
            usage = self.deepseek.last_usage
            if usage:
                pt = usage.get("prompt_tokens", 0)
                ct = usage.get("completion_tokens", 0)
                stats.record_tokens(pt, ct)
                req_prompt += pt
                req_completion += ct

            if not response:
                return "（LLM 响应失败）", all_files, {"prompt_tokens": req_prompt, "completion_tokens": req_completion}

            # 追踪：第一轮 LLM 思考完成
            if is_first_llm:
                is_first_llm = False
                if request_id:
                    _trace_event(request_id, "llm_first_done")

            content = response.get("content") or ""
            tool_calls = response.get("tool_calls")

            if not tool_calls:
                # 没有工具调用 → 最终回复
                if content.strip() != "__SKIP__":
                    self.recorder.record_assistant(user_id, content, tool_calls=None)
                return content, all_files, {"prompt_tokens": req_prompt, "completion_tokens": req_completion}

            # 有工具调用 → 记录 assistant 消息
            self.recorder.record_assistant(user_id, content, tool_calls=tool_calls)
            logger.info("LLM 请求 %d 个工具调用", len(tool_calls))

            # 添加 assistant 消息到上下文
            assistant_msg = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            has_final = False
            final_text = ""

            # 状态：操作中（有工具调用）
            # 逐个执行工具
            for tc in tool_calls:
                if tc.get("type") != "function":
                    continue
                func = tc.get("function", {})
                tool_name = func.get("name", "")

                # 状态：操作中
                tool_obj = tool_registry.get(tool_name)
                disp_name = tool_obj.display_name if tool_obj else tool_name
                ai_status.set("operating", message=f"正在调用 {disp_name}")

                # 追踪：工具调用开始
                if request_id:
                    _trace_event(request_id, "tool_call", metadata={"tool": tool_name})

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

                # 追踪：工具返回
                if request_id:
                    _trace_event(request_id, "tool_result", metadata={"tool": tool_name})

                # 收集附件文件
                files = result.get("files", [])
                if files:
                    all_files.extend(files)

                # 记录工具结果到 DB（含原始 tool_call_id）
                self.recorder.record_tool_result(user_id, tool_name, result,
                                                  tool_call_id=str(tc.get("id", "")))

                # 检查是否为 final 工具
                tool_obj = tool_registry.get(tool_name)
                if tool_obj and tool_obj.final:
                    # final 工具：不送回 LLM，直接返回结果
                    # 真正的工具调用结果已经由 record_tool_result 记录到 DB
                    # 在内存中加入 tool 响应和 assistant 响应，保证上下文链完整
                    tool_response = {"role": "tool", "tool_call_id": str(tc.get("id", "")),
                                     "content": json.dumps(result, ensure_ascii=False)}
                    assistant_response = {"role": "assistant", "content": result_text}
                    # DB：记录 assistant 响应
                    self.recorder.record_assistant(user_id, result_text)
                    # 内存
                    messages.append(tool_response)
                    messages.append(assistant_response)
                    has_final = True
                    final_text = result_text
                    break  # 跳出工具循环（不继续执行后面的工具）

                # 非 final 工具：将结果加入上下文，继续 LLM 循环
                messages.append({
                    "role": "tool",
                    "tool_call_id": str(tc.get("id", "")),
                    "content": json.dumps(result, ensure_ascii=False),
                })

            # 工具执行完毕，回到思考状态
            if not has_final:
                ai_status.set("thinking")

            if has_final:
                # 清理上下文中孤立的 tool_calls（final 工具不会添加 tool response）
                # 避免下次构建上下文时 DeepSeek 报错
                self._cleanup_orphan_tool_calls(messages)
                return final_text, all_files, {"prompt_tokens": req_prompt, "completion_tokens": req_completion}

        logger.warning("LLM 工具调用达到最大迭代次数 %d", self.MAX_ITERATIONS)
        return "（工具调用次数过多，请简化问题）", all_files, {"prompt_tokens": req_prompt, "completion_tokens": req_completion}

    @staticmethod
    def _cleanup_orphan_tool_calls(messages: list[dict]):
        """清理没有对应 tool response 的 tool_calls 消息"""
        i = 0
        while i < len(messages):
            msg = messages[i]
            if isinstance(msg, dict) and msg.get("tool_calls"):
                tc_ids = {tc["id"] for tc in msg["tool_calls"]}
                j = i + 1
                while j < len(messages):
                    nxt = messages[j]
                    if isinstance(nxt, dict) and nxt.get("role") == "tool":
                        tc_ids.discard(nxt.get("tool_call_id", ""))
                        j += 1
                    else:
                        break
                if tc_ids:
                    logger.debug("清理孤立 tool_calls: %s", tc_ids)
                    messages.pop(i)
                    continue
            i += 1
