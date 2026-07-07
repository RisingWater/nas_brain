# deploy/start_scripts/service_manager.py
import os
import sys
import subprocess
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
os.chdir(project_root)

if __name__ == "__main__":
    host = os.getenv("SERVICE_MANAGER_HOST", "0.0.0.0")
    port = str(os.getenv("SERVICE_MANAGER_PORT", "9022"))
    config = os.getenv("SERVICE_MANAGER_CONFIG", "deploy/service_config.json")

    print(f"🚀 启动微服务管理器")
    print(f"   http://{host}:{port}")
    print(f"   📋 配置文件: {config}")
    print("-" * 50)

    cmd = [
        sys.executable, "-m", "uvicorn",
        "src.service_manager.app:app",
        "--host", host,
        "--port", port,
    ]
    subprocess.run(cmd)
