"""智学网 API 客户端 — 获取考试成绩"""
import logging
import time
import json
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class ZhixueAPI:
    """智学网 API 客户端"""

    def __init__(self):
        self._base_url = "https://ali-bg.zhixue.com"
        self._device_id = "e640163b58dd034bd6872f7df7d60175"
        self._tgt = "TGT-144825-mw0IcWffVT2utvm9YtMkgsaEWtHHzCAACbHwXgk04bfS1ObvHe-open.changyan.com"
        self._token = self._get_token()

        # 学年度时间计算
        now = datetime.now()
        if now.month >= 8:
            start_year = now.year
            end_year = now.year + 1
        else:
            start_year = now.year - 1
            end_year = now.year

        start_ts = int(datetime(start_year, 8, 1, 0, 0, 0).timestamp() * 1000)
        end_ts = int(datetime(end_year, 7, 31, 23, 59, 59).timestamp() * 1000)
        self._start_school_year = start_ts
        self._end_school_year = end_ts

    def _get_at_token(self):
        """获取 AT token"""
        url = "https://open.changyan.com/sso/v1/api"
        headers = {"User-Agent": "zhixue_student/1.0.2047 (iPhone; iOS 26.2.1; Scale/3.00)"}
        data = {
            "appId": "zhixue_student",
            "client": "ios",
            "deviceId": self._device_id,
            "deviceName": "iPhone18,3",
            "extInfo": f'{{"deviceId":"{self._device_id}"}}',
            "method": "sso.extend.tgt",
            "ncetAppId": "SDZSH23Z6LPnq8iCweQrUo5ACJXtKCvG",
            "networkState": "wifi",
            "osType": "ios",
            "tgt": self._tgt,
            "userProxy": "true",
        }
        try:
            resp = requests.post(url, headers=headers, data=data, timeout=15)
            result = resp.json()
            if result.get("code") == "success":
                return result.get("data")
            logger.error("获取 AT 失败: %s", result.get("message"))
        except Exception as e:
            logger.error("获取 AT 异常: %s", e)
        return None

    def _get_token(self):
        """智学网 CAS 登录，获取 token"""
        at_data = self._get_at_token()
        if not at_data:
            return None

        at_token = at_data.get("at")
        user_id = at_data.get("userId")
        url = "https://www.zhixue.com/container/app/login/casLogin"
        headers = {
            "Host": "www.zhixue.com",
            "sucOriginAppKey": "zhixue_student",
            "User-Agent": "zhixue_student/1.0.2047 (iPhone; iOS 26.2.1; Scale/3.00)",
            "deviceId": self._device_id,
            "deviceName": "iPhone",
            "appName": "com.zhixue.student",
            "sucAccessDeviceId": self._device_id,
        }
        data = {
            "appId": "zhixue_student",
            "at": at_token,
            "ncetAppId": "SDZSH23Z6LPnq8iCweQrUo5ACJXtKCvG",
            "tokenTimeout": "0",
            "userId": user_id,
        }
        try:
            resp = requests.post(url, headers=headers, data=data, timeout=15)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("success") and result.get("errorCode") == 0:
                    token = result.get("result", {}).get("token", "")
                    logger.info("智学网登录成功")
                    return token
                logger.error("智学网登录失败: %s", result.get("errorInfo"))
        except Exception as e:
            logger.error("智学网登录异常: %s", e)
        return None

    def get_exam_list(self) -> list:
        """获取考试列表"""
        url = f"{self._base_url}/zhixuebao/report/exam/getUserExamList"
        params = {
            "pageIndex": 1,
            "pageSize": 10,
            "startSchoolYear": self._start_school_year,
            "endSchoolYear": self._end_school_year,
        }
        headers = {"XToken": self._token, "token": self._token}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("errorCode") == 0:
                    exams = []
                    for exam in data["result"]["examList"]:
                        exams.append({
                            "examId": exam["examId"],
                            "examName": exam["examName"],
                            "examType": exam["examType"],
                        })
                    return exams
                logger.error("API 返回错误: %s", data.get("errorInfo"))
        except Exception as e:
            logger.error("获取考试列表异常: %s", e)
        return []

    def get_exam_report(self, exam_id: str) -> list:
        """获取考试报告"""
        url = f"{self._base_url}/zhixuebao/report/exam/getReportMain"
        params = {"examId": exam_id}
        headers = {"XToken": self._token, "token": self._token}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("errorCode") == 0:
                    papers = []
                    for paper in data["result"]["paperList"]:
                        papers.append({
                            "paperId": paper["paperId"],
                            "examId": exam_id,
                            "paperName": paper["paperName"],
                            "subjectName": paper["subjectName"],
                            "userScore": paper["userScore"],
                            "standardScore": paper["standardScore"],
                        })
                    return papers
                logger.error("API 返回错误: %s", data.get("errorInfo"))
        except Exception as e:
            logger.error("获取考试报告异常: %s", e)
        return []
