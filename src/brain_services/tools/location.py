"""QB 设备位置查询工具"""
import os
import logging
import requests
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.location")

_QB_URL = os.getenv("QB_LOCATION_URL", "")
_QB_USERNAME = os.getenv("QB_LOCATION_USERNAME", "")
_QB_PASSWORD = os.getenv("QB_LOCATION_PASSWORD", "")
_QB_AUTHORITY = os.getenv("QB_LOCATION_AUTHORITY", "")

_BASE_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "client_type": "pc",
    "content-type": "application/json",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_BASE_HEADERS)
    s.headers.update({"authority": _QB_AUTHORITY, "origin": _QB_URL, "referer": f"{_QB_URL}/login"})
    return s


def _login(s: requests.Session) -> bool:
    resp = s.post(f"{_QB_URL}/api/sys/loginout/login",
                  json={"loginName": _QB_USERNAME, "password": _QB_PASSWORD}, timeout=10)
    data = resp.json()
    if data.get("code") != 1000: return False
    s.headers.update({"token": data["data"]["token"]})
    return True


def _get_device() -> dict | None:
    if not _QB_URL: return None
    s = _session()
    if not _login(s): s.close(); return None
    resp = s.get(f"{_QB_URL}/api/device/locationManager/getOfficeDeviceTreeData",
                 params={"size": 100, "current": 1}, timeout=10)
    s.close()
    devices = resp.json().get("data", {}).get("records", [])
    yuqiao = [d for d in devices if "乔宝" in d.get("name", "")]
    return yuqiao[0] if yuqiao else (devices[0] if devices else None)


def _get_address(s: requests.Session, device: dict) -> str | None:
    detail = s.post(f"{_QB_URL}/api/device/locationManager/getCurrPointInfoAll",
                    json={"deviceIdList": [device["id"]], "excludeLbs": 1}, timeout=10)
    dd = detail.json()
    if dd.get("code") != 1000 or not dd.get("data"): return None
    addr = s.post(f"{_QB_URL}/api/device/locationManager/batchAddress",
                  json={"pointList": [{"lat": device["latitude"], "lon": device["longitude"],
                                       "infoType": device.get("infoType", 3)}]}, timeout=10)
    ad = addr.json()
    return ad["data"][0] if ad.get("code") == 1000 and ad.get("data") else None


class YuqiaoLocationTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="get_yuqiao_location",
            description="查询煜乔的当前位置。返回设备名称、电量和详细地址。",
            parameters={"type": "object", "properties": {}, "required": []},
        )

    def execute(self, args: dict) -> str:
        if not _QB_URL: return "QB 定位未配置"
        try:
            d = _get_device()
            if not d: return "未找到设备"
            s = _session()
            if not _login(s): s.close(); return "登录失败"
            name = d["name"]
            power = d.get("power", "?")
            addr = _get_address(s, d)
            s.close()
            if addr: return f"{name}（电量 {power}%）— {addr}"
            return f"{name}（电量 {power}%）— 地址获取失败"
        except Exception as e:
            return f"查询位置失败: {e}"


class YuqiaoPowerTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="get_yuqiao_power",
            description="查询煜乔的通话器剩余电量，返回电量百分比。",
            parameters={"type": "object", "properties": {}, "required": []},
        )

    def execute(self, args: dict) -> str:
        if not _QB_URL: return "QB 定位未配置"
        try:
            d = _get_device()
            if not d: return "未找到设备"
            return f"{d['name']} 当前电量 {d.get('power', '?')}%"
        except Exception as e:
            return f"查询电量失败: {e}"


registry.register(YuqiaoLocationTool())
registry.register(YuqiaoPowerTool())
