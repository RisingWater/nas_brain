"""db_services HTTP 客户端 — 通过 REST API 访问数据库微服务"""
import os
import requests
from typing import Optional, Dict, Any
from src.db_services.schema.user_schema import (
    AddUserRequest, UpdateUserRequest, UserResponse, ListUsersResponse
)
from src.common.utils import cfg


class DbClient:
    """封装对 db_services 的 HTTP 调用（复用连接池）"""

    def __init__(self):
        self._session = requests.Session()
        self._base = cfg.get_service_url("db_services", "/api/users")

    # ---- 用户 CRUD ----

    def list_users(
        self,
        user_type: Optional[str] = None,
        keyword: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """获取用户列表（分页），返回 {total, users, page, page_size}"""
        params = {"limit": page_size, "offset": (page - 1) * page_size}
        if user_type:
            params["user_type"] = user_type
        if keyword:
            params["keyword"] = keyword
        if is_active is not None:
            params["is_active"] = str(is_active).lower()

        resp = self._session.get(self._base, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {
            "total": data["total"],
            "users": data["users"],
            "page": page,
            "page_size": page_size,
        }

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取单个用户"""
        resp = self._session.get(f"{self._base}/{user_id}", timeout=10)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def create_user(self, data: AddUserRequest) -> Dict[str, Any]:
        """创建用户"""
        resp = self._session.post(
            self._base,
            json=data.model_dump(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def update_user(self, user_id: str, data: UpdateUserRequest) -> Dict[str, Any]:
        """更新用户"""
        resp = self._session.put(
            f"{self._base}/{user_id}",
            json=data.model_dump(exclude_none=True),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def delete_user(self, user_id: str) -> Dict[str, Any]:
        """删除用户"""
        resp = self._session.delete(f"{self._base}/{user_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()


# 全局单例
db_client = DbClient()
