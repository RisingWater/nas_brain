"""ServiceManager — 微服务子进程管理器"""
import json
import logging
import os
import shlex
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional

logger = logging.getLogger("service_manager")


def _find_project_root() -> str:
    """从当前文件位置向上查找项目根目录（包含 deploy 目录）"""
    path = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        if os.path.isdir(os.path.join(path, "deploy")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return os.getcwd()


class ServiceInfo:
    """单个服务的运行时信息"""

    def __init__(self, name: str, command: str, description: str = "", enable: bool = True):
        self.name = name
        self.command = command
        self.description = description
        self.enable = enable
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self._lock = threading.Lock()

    @property
    def status(self) -> str:
        if not self.enable:
            return "disabled"
        if self.process is None:
            return "stopped"
        ret = self.process.poll()
        if ret is None:
            return "running"
        return f"exited({ret})"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "command": self.command,
            "description": self.description,
            "enable": self.enable,
            "status": self.status,
            "pid": self.process.pid if self.process and self.process.poll() is None else None,
        }


class ServiceManager:
    """微服务管理器 — 子进程启停"""

    def __init__(self, config_path: str):
        self._project_root = _find_project_root()
        self._services: Dict[str, ServiceInfo] = {}
        self._load_config(config_path)

    # ---- 配置 ----

    def _load_config(self, config_path: str):
        """读取 JSON 配置文件"""
        if not os.path.isabs(config_path):
            config_path = os.path.join(self._project_root, config_path)
        with open(config_path, encoding="utf-8") as f:
            entries = json.load(f)
        for entry in entries:
            svc = ServiceInfo(
                name=entry["name"],
                command=entry["command"],
                description=entry.get("description", ""),
                enable=entry.get("enable", True),
            )
            self._services[svc.name] = svc

    @property
    def services(self) -> List[ServiceInfo]:
        return list(self._services.values())

    def get(self, name: str) -> Optional[ServiceInfo]:
        return self._services.get(name)

    # ---- 启停 ----

    def start_all(self):
        """启动所有开启的服务"""
        for svc in self._services.values():
            if svc.enable:
                self._start_one(svc)

    def stop_all(self):
        """停止所有服务"""
        for svc in self._services.values():
            self._stop_one(svc)

    def start(self, name: str) -> bool:
        """启动指定服务"""
        svc = self._services.get(name)
        if not svc:
            return False
        return self._start_one(svc)

    def stop(self, name: str) -> bool:
        """停止指定服务"""
        svc = self._services.get(name)
        if not svc:
            return False
        return self._stop_one(svc)

    def restart(self, name: str) -> bool:
        """重启指定服务"""
        svc = self._services.get(name)
        if not svc:
            return False
        self._stop_one(svc)
        return self._start_one(svc)

    def set_enable(self, name: str, enable: bool) -> Optional[ServiceInfo]:
        """设置服务的 enable 状态，并同步到配置文件"""
        svc = self._services.get(name)
        if not svc:
            return None
        svc.enable = enable
        if not enable:
            self._stop_one(svc)  # 禁用时自动停止
        self._save_config()
        return svc

    def _save_config(self):
        """将当前服务配置写回 JSON 文件"""
        config_path = os.getenv("SERVICE_MANAGER_CONFIG", "deploy/service_config.json")
        if not os.path.isabs(config_path):
            config_path = os.path.join(self._project_root, config_path)
        entries = []
        for svc in self._services.values():
            entries.append({
                "name": svc.name,
                "description": svc.description,
                "command": svc.command,
                "enable": svc.enable,
            })
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)

    # ---- 内部 ----

    def _start_one(self, svc: ServiceInfo) -> bool:
        with svc._lock:
            if svc.process and svc.process.poll() is None:
                return True  # 已在运行
            try:
                cmd = shlex.split(svc.command)
                # 用当前 venv 的 Python，而不是 PATH 里的
                if cmd and cmd[0] in ("python", "python3"):
                    cmd[0] = sys.executable
                svc.process = subprocess.Popen(
                    cmd,
                    cwd=self._project_root,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                svc.pid = svc.process.pid
                return True
            except Exception as e:
                logger.error("启动 %s 失败: %s", svc.name, e)
                svc.process = None
                svc.pid = None
                return False

    def _stop_one(self, svc: ServiceInfo) -> bool:
        with svc._lock:
            proc = svc.process
            if not proc or proc.poll() is not None:
                svc.process = None
                svc.pid = None
                return True  # 已停止
            try:
                proc.terminate()  # POSIX: SIGTERM, Windows: TerminateProcess
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()  # POSIX: SIGKILL, Windows: TerminateProcess
                    proc.wait(timeout=3)
            except Exception as e:
                logger.error("停止 %s 失败: %s", svc.name, e)
            finally:
                svc.process = None
                svc.pid = None
            return True
