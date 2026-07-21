"""KV Store 客户端 — 通过 db_services 的 /api/kv 存取键值对"""
import logging
import requests
from src.common.utils import cfg

logger = logging.getLogger(__name__)

_KV_BASE = cfg.get_service_url("db_services", "/api/kv")


class KVStore:
    """分布式 KV 存储（基于 db_services 的 kv_store 表）"""

    def get(self, key: str, default: str | None = None) -> str | None:
        try:
            resp = requests.get(f"{_KV_BASE}/{key}", timeout=5)
            if resp.status_code == 200:
                return resp.json().get("value")
            if resp.status_code == 404:
                return default
        except Exception as e:
            logger.warning("KV get 失败 (%s): %s", key, e)
        return default

    def set(self, key: str, value: str, namespace: str = ""):
        """写入键值对"""
        try:
            requests.put(f"{_KV_BASE}/{key}", json={"value": value, "namespace": namespace}, timeout=5)
        except Exception as e:
            logger.warning("KV set 失败 (%s): %s", key, e)

    def delete(self, key: str):
        try:
            requests.delete(f"{_KV_BASE}/{key}", timeout=5)
        except Exception as e:
            logger.warning("KV delete 失败 (%s): %s", key, e)

    def exists(self, key: str) -> bool:
        return self.get(key) is not None


# 全局单例
kv_store = KVStore()
