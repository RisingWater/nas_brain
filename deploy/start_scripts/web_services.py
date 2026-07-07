# scripts/start_web_services.py
import os
import sys
import subprocess
import argparse
from pathlib import Path

# 切换到项目根目录
project_root = Path(__file__).parent.parent.parent
os.chdir(project_root)
print(f"项目根目录: {project_root}")


def main():
    parser = argparse.ArgumentParser(description="启动管理后端微服务")
    parser.add_argument("--reload", action="store_true", help="热加载模式")
    args = parser.parse_args()

    host = os.getenv("WEB_SERVICE_HOST", "0.0.0.0")
    port = str(os.getenv("WEB_SERVICE_PORT", "9020"))

    os.environ["LOG_SERVER_NAME"] = "web_services"

    cmd = [
        sys.executable, "-m", "uvicorn",
        "src.web_services.app:app",
        "--host", host,
        "--port", port,
    ]

    if args.reload:
        cmd.append("--reload")
        cmd.append("--reload-dir")
        cmd.append("src/web_services")

    print(f"🚀 启动管理后端微服务")
    print(f"   http://{host}:{port}")
    print(f"   📝 日志名: {os.environ['LOG_SERVER_NAME']}")
    print(f"   🔄 热加载: {'开启' if '--reload' in cmd else '关闭'}")
    print("-" * 50)

    subprocess.run(cmd)


if __name__ == "__main__":
    main()
