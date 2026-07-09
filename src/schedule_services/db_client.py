"""schedule_services — db_services HTTP 客户端"""
import logging
import requests
from typing import Optional, Any
from src.common.utils import cfg

logger = logging.getLogger("schedule_services")


class ScheduleDbClient:
    """封装对 db_services 的 schedules API 调用"""

    def __init__(self):
        self._base = cfg.get_service_url("db_services", "/api/schedules")

    def _url(self, path: str = "") -> str:
        return f"{self._base}{path}"

    def list_all(self, done: Optional[bool] = None) -> list[dict]:
        """全量拉取 schedules"""
        params = {"limit": 1000}
        if done is not None:
            params["done"] = str(done).lower()
        resp = requests.get(self._url(), params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("schedules", [])

    def get(self, schedule_id: int) -> Optional[dict]:
        resp = requests.get(self._url(f"/{schedule_id}"), timeout=10)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def create(self, data: dict) -> dict:
        resp = requests.post(self._url(), json=data, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def update(self, schedule_id: int, data: dict) -> dict:
        resp = requests.put(self._url(f"/{schedule_id}"), json=data, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def delete(self, schedule_id: int) -> dict:
        resp = requests.delete(self._url(f"/{schedule_id}"), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def mark_done(self, schedule_id: int) -> dict:
        resp = requests.post(self._url(f"/{schedule_id}/mark-done"), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_stats(self) -> dict:
        resp = requests.get(self._url("/stats"), timeout=10)
        resp.raise_for_status()
        return resp.json()


# 全局单例
db_client = ScheduleDbClient()
