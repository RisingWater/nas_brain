"""
配置 — Config 单例从 .env 加载全部可调参数

服务发现：
  SINGLETON=1 (默认) → 所有微服务互连用 127.0.0.1
  SINGLETON=0       → 从 deploy/services_registry.json 读取各服务 IP
"""
import json
import os
from dotenv import load_dotenv

_REGISTRY_FILE = "deploy/services_registry.json"

# 微服务端口映射（默认端口，env 可覆盖）
_SERVICE_PORTS: dict[str, tuple[str, str]] = {
    "db_services":      ("DB_SERVICE_PORT",      "9021"),
    "web_services":     ("WEB_SERVICE_PORT",     "9020"),
    "service_manager":  ("SERVICE_MANAGER_PORT", "9022"),
    "wechat_gateway":   ("WECHAT_GATEWAY_PORT",  "9030"),
    "brain_services":   ("BRAIN_SERVICE_PORT",   "9031"),
    "playback_services": ("PLAYBACK_SERVICE_PORT", "9041"),
    "timer_services":   ("TIMER_SERVICE_PORT",   "9040"),
}


class ConfigManager:
    """应用配置单例"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    @classmethod
    def instance(cls):
        return cls()

    def _load(self):
        load_dotenv(override=True)

        # ---- 运行模式 ----
        self.SINGLETON = os.getenv("SINGLETON", "1") == "1"
        self._registry: dict[str, dict] = {}  # 服务名 → {"host": ..., "port": ...}

        if self.SINGLETON:
            # 单机模式：所有服务 localhost 互连
            self._host = "127.0.0.1"
        else:
            # 多机模式：从注册表文件读取各服务地址
            self._host = None
            self._load_registry()

        # LOG
        self.LOG_DIR = os.getenv("LOG_DIR", "logs")
        self.LOG_SIZE = int(os.getenv("LOG_SIZE", "20")) * 1024 * 1024
        self.LOG_BACKUPS = int(os.getenv("LOG_BACKUP", "3"))
        self.LOG_MAX_ENTRYS = int(os.getenv("LOG_MAX_ENTRY", "20000"))

        # WXAUTO API
        self.WXAUTO_API_URL = os.getenv("WXAUTO_API_URL", "")
        self.WXAUTO_API_TOKEN = os.getenv("WXAUTO_API_TOKEN", "")

        # DB
        self.DB_PATH = os.getenv("DB_PATH", "data/db/users.db")
        self.DB_SERVICE_PORT = int(os.getenv("DB_SERVICE_PORT", "9021"))

    def _load_registry(self):
        """从 JSON 加载多机服务注册表"""
        path = os.getenv("SERVICE_REGISTRY_PATH", _REGISTRY_FILE)
        if not os.path.isabs(path):
            project_root = self._find_project_root()
            path = os.path.join(project_root, path)
        try:
            with open(path, encoding="utf-8") as f:
                self._registry = json.load(f)
        except Exception as e:
            raise RuntimeError(f"多机模式需要服务注册表文件: {path} ({e})")

    @staticmethod
    def _find_project_root() -> str:
        path = os.path.dirname(os.path.abspath(__file__))
        for _ in range(10):
            if os.path.isdir(os.path.join(path, "deploy")):
                return path
            parent = os.path.dirname(path)
            if parent == path:
                break
            path = parent
        return os.getcwd()

    # ---- 服务发现 API ----

    def get_service_addr(self, service_name: str) -> tuple[str, int]:
        """获取微服务的 (host, port)"""
        if self.SINGLETON:
            host = "127.0.0.1"
        else:
            entry = self._registry.get(service_name, {})
            host = entry.get("host", "127.0.0.1")

        port_info = _SERVICE_PORTS.get(service_name)
        if port_info:
            port = int(os.getenv(port_info[0], port_info[1]))
        else:
            port = 0
        return host, port

    def get_service_url(self, service_name: str, path: str = "") -> str:
        """获取微服务的 HTTP base URL，如 http://127.0.0.1:9021/api/users"""
        host, port = self.get_service_addr(service_name)
        return f"http://{host}:{port}{path}"


# 全局单例
cfg = ConfigManager()
