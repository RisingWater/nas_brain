# scripts/start_db_services.py
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
    parser = argparse.ArgumentParser(description="启动数据库微服务")
    parser.add_argument("--reload", action="store_true", help="热加载模式")
    args = parser.parse_args()
    
    # 从环境变量读取配置
    host = os.getenv("DB_SERVCIE_HOST", "0.0.0.0")
    port = str(os.getenv("DB_SERVCIE_PORT", "9021"))
    
    # 确保数据目录存在
    os.makedirs("data/db", exist_ok=True)

    os.environ["LOG_SERVER_NAME"] = "db_services"
    
    # 构建命令
    cmd = [
        sys.executable, "-m", "uvicorn",
        "src.db_services.app:app",
        "--host", host,
        "--port", port,
    ]
    
    if args.reload:
        cmd.append("--reload")
        cmd.append("--reload-dir")
        cmd.append("src/db_services")
    
    print(f"🚀 启动数据库微服务")
    print(f"   http://{host}:{port}")
    print(f"   📂 数据库: {os.getenv('DB_PATH', 'data/db/users.db')}")
    print(f"   📝 日志名: {os.environ['LOG_SERVER_NAME']}")
    print(f"   🔄 热加载: {'开启' if '--reload' in cmd else '关闭'}")
    print("-" * 50)
    
    # 启动
    subprocess.run(cmd)


if __name__ == "__main__":
    main()