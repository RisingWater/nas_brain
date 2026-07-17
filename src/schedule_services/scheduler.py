"""调度引擎 — 每 60 秒遍历所有 detector 执行 process_loop()"""
import logging
import threading
import time
from .detector.base import DetectorContext, registry

logger = logging.getLogger("schedule_services")

_TICK_INTERVAL = 60  # 主循环间隔（秒）


class Scheduler:
    """调度引擎，独立线程运行"""

    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None
        self.ctx = DetectorContext()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="scheduler")
        self._thread.start()
        logger.info("调度引擎已启动 (tick=%ds)", _TICK_INTERVAL)

    def stop(self):
        self._running = False
        logger.info("调度引擎已停止")

    def _run_loop(self):
        while self._running:
            try:
                tick_start = time.time()
                detectors = registry.get_all()
                for d in detectors:
                    if not d.enable:
                        continue
                    if time.time() - d.last_run >= d.interval:
                        logger.debug("执行 detector: %s (interval=%ds)", d.name, d.interval)
                        try:
                            d.process_loop(self.ctx)
                        except Exception as e:
                            logger.error("Detector %s 异常: %s", d.name, e, exc_info=True)
                        d.last_run = time.time()

                elapsed = time.time() - tick_start
                sleep_time = max(1, _TICK_INTERVAL - elapsed)
                time.sleep(sleep_time)

            except Exception as e:
                logger.error("调度主循环异常: %s", e, exc_info=True)
                time.sleep(_TICK_INTERVAL)
