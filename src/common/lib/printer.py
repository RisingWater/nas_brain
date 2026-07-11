"""CUPS 网络打印机客户端 — 跨平台，通过 IPP 打印 PDF"""
import os
import logging

logger = logging.getLogger(__name__)


class Printer:
    """CUPS 打印机（连接 .env 中配置的网络打印机）"""

    def __init__(self):
        self._printer_name = os.getenv("PRINTER_NAME", "")
        self._conn = None
        if not self._printer_name:
            logger.warning("PRINTER_NAME 未设置，打印功能不可用")
        else:
            self._connect()

    def _connect(self):
        try:
            import cups
            self._conn = cups.Connection()
            logger.info("已连接 CUPS 服务器")
        except ImportError:
            logger.warning("pycups 未安装，打印功能不可用 (pip install pycups)")
            self._conn = None
        except Exception as e:
            logger.error("连接 CUPS 失败: %s", e)
            self._conn = None

    @property
    def is_ready(self) -> bool:
        return bool(self._conn and self._printer_name)

    def print_pdf(self, pdf_path: str, color: bool = True) -> tuple[bool, str | None]:
        """打印 PDF，返回 (success, job_id)"""
        if not self.is_ready:
            return False, "打印机未就绪"
        try:
            options = {}
            if not color:
                options["ColorModel"] = "Gray"
            job_id = self._conn.printFile(self._printer_name, pdf_path, "print_job", options)
            logger.info("打印任务已创建: %s (job_id=%s)", pdf_path, job_id)
            return True, str(job_id)
        except Exception as e:
            logger.error("打印失败: %s", e)
            return False, str(e)

    def get_job_status(self, job_id: str) -> dict:
        """查询打印任务状态"""
        if not self._conn:
            return {"state_name": "unknown"}
        try:
            jobs = self._conn.getJobs()
            for jid, attrs in jobs.items():
                if str(jid) == job_id:
                    return {
                        "job_id": jid,
                        "state_name": attrs.get("job-state", ""),
                        "state_reasons": attrs.get("job-state-reasons", ""),
                    }
            return {"job_id": job_id, "state_name": "completed"}
        except Exception as e:
            return {"state_name": "error", "error": str(e)}
