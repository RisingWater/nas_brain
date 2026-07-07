"""
配置 — Config 单例从 .env 加载全部可调参数
"""
import os
from dotenv import load_dotenv

class ConfigManager:
    """应用配置单例，从 .env 加载"""

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
        load_dotenv()

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
        self.DB_SERVICE_PORT = int(os.getenv("DB_SERVICE_PORT", "9001"))



# 全局单例
cfg = ConfigManager()
