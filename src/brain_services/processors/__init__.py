"""Processor 处理器插件系统 — BaseProcessor + ProcessorContext + ProcessorRegistry

与 tool/detector 同模式，支持热加载。"""
import os
import logging
from typing import Optional
from src.common.schemas.agent_request import AgentRequest, ProtocolType, ContentType

logger = logging.getLogger("brain_services.processors")


class ProcessorContext:
    """给处理器的上下文，封装发送响应等能力"""

    def __init__(self, req: AgentRequest):
        self.req = req
        self._replied = False

    @property
    def has_replied(self) -> bool:
        """是否已回复（processor 可据此判断是否需要 fallback）"""
        return self._replied

    def reply(self, msg: str):
        """回复到来源（暂存，由 agent route 发送）"""
        self._reply_text = msg
        self._replied = True

    def send_wechat(self, who: str, msg: str):
        """发送微信文本消息"""
        import requests as _req
        from src.common.utils import cfg
        try:
            url = cfg.get_service_url("wechat_gateway", "/api/gateway/send-text")
            _req.post(url, json={"who": who, "msg": msg}, timeout=10)
        except Exception as e:
            logger.error("发送微信失败: %s", e)

    def send_wechat_file(self, who: str, file_path: str, filename: str = ""):
        """发送微信文件"""
        import requests as _req
        from src.common.utils import cfg
        try:
            url = cfg.get_service_url("wechat_gateway", "/api/gateway/send-file")
            with open(file_path, "rb") as f:
                _req.post(
                    url,
                    data={"who": who, "wxname": ""},
                    files={"file": (filename or os.path.basename(file_path), f, "application/octet-stream")},
                    timeout=30,
                )
            logger.info("文件已发送到 %s: %s", who, file_path)
        except Exception as e:
            logger.error("发送微信文件失败: %s", e)

    def download_file(self, file_id: str) -> Optional[bytes]:
        """从 wechat_gateway 下载文件"""
        import requests as _req
        from src.common.utils import cfg
        try:
            url = cfg.get_service_url("wechat_gateway", f"/api/gateway/files/{file_id}/download")
            resp = _req.get(url, timeout=30)
            if resp.status_code == 200:
                return resp.content
        except Exception as e:
            logger.error("下载文件失败: %s", e)
        return None


class BaseProcessor:
    """处理器基类。子类需设置 name、description、priority 并实现 can_handle/handle"""

    name: str = ""
    description: str = ""

    def priority(self) -> int:
        return 100

    def can_handle(self, req: AgentRequest) -> bool:
        return False

    def handle(self, req: AgentRequest, ctx: ProcessorContext) -> dict | None:
        """处理请求，返回 {"reply": "xxx"} 或 None（未处理）"""
        raise NotImplementedError


class ProcessorRegistry:
    """Processor 注册表（单例，支持热加载）"""

    _instance: Optional["ProcessorRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._processors: dict[str, BaseProcessor] = {}

    def register(self, p: BaseProcessor):
        self._processors[p.name] = p
        logger.info("注册 processor: %s", p.name)

    def unregister(self, name: str):
        self._processors.pop(name, None)

    def get(self, name: str) -> Optional[BaseProcessor]:
        return self._processors.get(name)

    def get_all(self) -> list[BaseProcessor]:
        return list(self._processors.values())

    def get_sorted(self) -> list[BaseProcessor]:
        """按 priority 升序排列（越小越优先）"""
        return sorted(self._processors.values(), key=lambda p: p.priority())

    def clear(self):
        self._processors.clear()

    def to_list(self) -> list[dict]:
        return [
            {"name": p.name, "description": p.description, "priority": p.priority(),
             "class": p.__class__.__name__}
            for p in self._processors.values()
        ]

    def find_handler(self, req: AgentRequest) -> tuple[Optional[BaseProcessor], Optional[ProcessorContext]]:
        """按 priority 遍历，返回第一个 can_handle 的 (processor, context)"""
        ctx = ProcessorContext(req)
        for p in self.get_sorted():
            try:
                if p.can_handle(req):
                    return p, ctx
            except Exception as e:
                logger.error("Processor %s.can_handle 异常: %s", p.name, e)
        return None, ctx


# 全局单例
registry = ProcessorRegistry()
