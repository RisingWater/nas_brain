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

    MAX_ITERATIONS = 50  # 防止工具调用死循环

    def __init__(self):
        self.deepseek = DeepSeekAPI()
        self.recorder = ChatRecorder()

    def handle(self, user_id: str, messages: list[dict],
               tools: list[dict], request_id: str = "",
               final_enabled: bool = True) -> tuple[str, list[str], dict]:
        """函数调用循环：LLM → 工具 → LLM → ... → 最终回复

        Args:
            final_enabled: 是否启用工具 final 属性。
                启用时 final 工具执行后直接返回结果（适合语音，延迟敏感）；
                禁用时所有工具按正常逻辑执行，结果送回 LLM 继续处理（适合微信，避免伪造响应）。
                ice_breaker 无工具调用，不受影响。

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
            final_texts = []
            final_tool_responses = []

            # 逐个执行工具
            for tc in tool_calls:
                if tc.get("type") != "function":
                    continue
                func = tc.get("function", {})
                tool_name = func.get("name", "")

                tool_obj = tool_registry.get(tool_name)
                disp_name = tool_obj.display_name if tool_obj else tool_name
                ai_status.set("operating", message=f"正在调用 {disp_name}")

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
                try:
                    result = tool_registry.execute(tool_name, args)
                except Exception as e:
                    # 工具异常也写入 tool 响应（错误信息）：保证 DB 里
                    # assistant(tool_calls) 与 tool 响应永远配对完整，
                    # 后续构建上下文不会出现孤立 tool_calls 触发 400
                    logger.error("工具 %s 执行异常: %s", tool_name, e, exc_info=True)
                    result = {"text": f"工具执行失败: {e}", "error": str(e)}
                result_text = result.get("text", "（无返回）")
                logger.info("工具 %s 返回: %.100s", tool_name, result_text)

                if request_id:
                    _trace_event(request_id, "tool_result", metadata={"tool": tool_name})

                files = result.get("files", [])
                if files:
                    all_files.extend(files)

                self.recorder.record_tool_result(user_id, tool_name, result,
                                                  tool_call_id=str(tc.get("id", "")))

                tool_obj = tool_registry.get(tool_name)
                if final_enabled and tool_obj and tool_obj.final:
                    final_tool_responses.append({
                        "role": "tool", "tool_call_id": str(tc.get("id", "")),
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                    final_texts.append(result_text)
                    has_final = True
                    continue

                messages.append({
                    "role": "tool",
                    "tool_call_id": str(tc.get("id", "")),
                    "content": json.dumps(result, ensure_ascii=False),
                })

            if has_final:
                # 所有 final 工具执行完毕：合并成一条 assistant 回复
                combined = "\n".join(final_texts) if len(final_texts) > 1 else (final_texts[0] if final_texts else "")
                for tr in final_tool_responses:
                    messages.append(tr)
                if combined:
                    self.recorder.record_assistant(user_id, combined)
                    messages.append({"role": "assistant", "content": combined})
                return combined, all_files, {"prompt_tokens": req_prompt, "completion_tokens": req_completion}

            # 非 final 工具，继续 LLM 循环
            ai_status.set("thinking", message="正在准备答复措辞")

        logger.warning("LLM 工具调用达到最大迭代次数 %d", self.MAX_ITERATIONS)
        return "（工具调用次数过多，请简化问题）", all_files, {"prompt_tokens": req_prompt, "completion_tokens": req_completion}
