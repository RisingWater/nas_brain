"""ServiceManager — 微服务子进程管理器"""
import json
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional


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

    def __init__(self, name: str, command: str, description: str = ""):
        self.name = name
        self.command = command
        self.description = description
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self._lock = threading.Lock()

    @property
    def status(self) -> str:
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
            )
            self._services[svc.name] = svc

    @property
    def services(self) -> List[ServiceInfo]:
        return list(self._services.values())

    def get(self, name: str) -> Optional[ServiceInfo]:
        return self._services.get(name)

    # ---- 启停 ----

    def start_all(self):
        """启动所有已注册的服务"""
        for svc in self._services.values():
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

    # ---- 内部 ----

    def _start_one(self, svc: ServiceInfo) -> bool:
        with svc._lock:
            if svc.process and svc.process.poll() is None:
                return True  # 已在运行
            try:
                cmd = shlex.split(svc.command)
                svc.process = subprocess.Popen(
                    cmd,
                    cwd=self._project_root,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                svc.pid = svc.process.pid
                return True
            except Exception as e:
                print(f"[service_manager] 启动 {svc.name} 失败: {e}")
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
                print(f"[service_manager] 停止 {svc.name} 失败: {e}")
            finally:
                svc.process = None
                svc.pid = None
            return True
