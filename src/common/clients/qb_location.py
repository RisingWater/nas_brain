"""QB 设备定位 API 客户端 — 获取设备电量/位置/地址"""
import os
import logging
import requests

logger = logging.getLogger(__name__)


class QBLocation:
    """QB 设备定位 API"""

    def __init__(self):
        self._base_url = os.getenv("QB_LOCATION_URL", "")
        self._username = os.getenv("QB_LOCATION_USERNAME", "")
        self._password = os.getenv("QB_LOCATION_PASSWORD", "")
        self._authority = os.getenv("QB_LOCATION_AUTHORITY", "")
        self._token = None
        self._session = requests.Session()
        self._setup_headers()

    def _setup_headers(self):
        self._session.headers.update({
            "authority": self._authority,
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9",
            "client_type": "pc",
            "content-type": "application/json",
            "origin": self._base_url,
            "referer": f"{self._base_url}/login",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })

    def _ensure_login(self) -> bool:
        if self._token:
            return True
        return self._login()

    def _login(self) -> bool:
        if not self._base_url or not self._username:
            logger.warning("QB_LOCATION 配置不完整")
            return False
        try:
            resp = self._session.post(
                f"{self._base_url}/api/sys/loginout/login",
                json={"loginName": self._username, "password": self._password},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 1000:
                    token = data.get("data", {}).get("token")
                    if token:
                        self._token = token
                        self._session.headers.update({"token": token})
                        return True
            logger.error("QB 登录失败: %s", resp.text[:200])
        except Exception as e:
            logger.error("QB 登录异常: %s", e)
        return False

    def _get_device_list(self) -> list:
        """获取设备列表"""
        if not self._ensure_login():
            return []
        try:
            resp = self._session.get(
                f"{self._base_url}/api/device/locationManager/getOfficeDeviceTreeData",
                params={"size": 100, "current": 1, "excludeLbs": 0},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 1000:
                    return data.get("data", {}).get("records", [])
        except Exception as e:
            logger.error("获取设备列表异常: %s", e)
        return []

    def get_power(self) -> list[dict]:
        """获取所有设备的电量信息"""
        devices = self._get_device_list()
        results = []
        for d in devices:
            results.append({
                "device_id": d.get("id"),
                "device_name": d.get("name", "未知"),
                "power": d.get("power", 100),
            })
        self._session.close()
        return results

    def get_location(self) -> list[dict]:
        """获取设备详细位置信息（含地址解析）"""
        devices = self._get_device_list()
        if not devices:
            self._session.close()
            return []

        results = []
        for device in devices:
            device_id = device["id"]
            device_name = device["name"]
            lat = device.get("latitude")
            lon = device.get("longitude")
            info_type = device.get("infoType", 3)
            power = device.get("power", 100)

            addr = self._get_address(device_id, lat, lon, info_type)
            results.append({
                "device_id": device_id,
                "device_name": device_name,
                "power": power,
                "latitude": lat,
                "longitude": lon,
                "address": addr or "地址获取失败",
            })

        self._session.close()
        return results

    def _get_address(self, device_id: int, lat: float, lon: float, info_type: int = 3) -> str | None:
        """通过 QB 的 batchAddress 获取地址描述"""
        try:
            # 先获取 modelId
            detail = self._session.post(
                f"{self._base_url}/api/device/locationManager/getCurrPointInfoAll",
                json={"deviceIdList": [device_id], "excludeLbs": 1},
                timeout=10,
            )
            if detail.status_code != 200:
                return None
            detail_data = detail.json()
            if detail_data.get("code") != 1000 or not detail_data.get("data"):
                return None

            model_id = detail_data["data"][0].get("modelId")

            # batchAddress
            addr = self._session.post(
                f"{self._base_url}/api/device/locationManager/batchAddress",
                json={"pointList": [{"lat": lat, "lon": lon, "infoType": info_type, "modelId": model_id}]},
                timeout=10,
            )
            if addr.status_code == 200:
                addr_data = addr.json()
                if addr_data.get("code") == 1000 and addr_data.get("data"):
                    return addr_data["data"][0]
        except Exception as e:
            logger.error("获取地址异常: %s", e)
        return None
