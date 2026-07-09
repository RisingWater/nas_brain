"""DSM 智能门禁 API 客户端 — 获取开门记录"""
import os
import re
import logging
import requests
from typing import List

logger = logging.getLogger(__name__)


class DSMSmartDoorAPI:
    """DSM 智能门禁 API"""

    def __init__(self):
        self._token = os.getenv("DSM_TOKEN", "")
        if not self._token:
            logger.warning("DSM_TOKEN 未设置，门禁功能不可用")

    def get_log(self) -> List[dict]:
        """获取今天的开门记录"""
        if not self._token:
            return []

        headers = {"token": self._token}
        url = ("https://nyuwa.dsmxp.com/nyuwa/dc/lock/log/open/door/type"
               "?lockId=2023111816472300760&pageNum=1&pageSize=20&type=1")

        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                logger.error("获取开门记录失败，状态码: %s", response.status_code)
                return []

            log_info = response.json()
            if not log_info.get("success") or log_info.get("status") != 1:
                logger.error("获取开门记录失败: %s", log_info.get("message", "未知错误"))
                return []

            loglist = []
            for record in log_info.get("data", []):
                log_date = record.get("logDate")
                if record.get("dayTag") == "今天":
                    for detail in record.get("logDetails", []):
                        if detail.get("logType") == "指纹开门":
                            log_time = detail.get("logTime")
                            names = re.findall(r"【(.*?)】", detail.get("content", ""))
                            if names:
                                loglist.append({
                                    "name": names[0],
                                    "timestamp": f"{log_date} {log_time}",
                                })
            return loglist

        except requests.RequestException as e:
            logger.error("获取开门记录异常: %s", e)
            return []
