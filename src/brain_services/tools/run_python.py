"""运行 Python 代码工具 — 写临时文件执行并返回结果"""
import os
import sys
import json
import logging
import subprocess
import tempfile
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.run_python")

_TEMP_DIR = os.path.normpath(os.getenv("TEMP_DIR", "data"))


class RunPythonTool(BaseTool):
    """运行 Python 代码"""

    def __init__(self):
        super().__init__(
            name="run_python",
            display_name="运行Python",
            description="运行一段 Python 代码，返回执行结果（stdout）。代码中可以读写 TEMP_DIR 目录下的文件来持久化数据。支持生成图片、图表等文件，文件会通过微信发送给用户。",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要执行的 Python 代码。代码中可以用 `os.environ.get('TEMP_DIR', 'data')` 获取临时目录路径",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时秒数（默认 30，最大 120）",
                    },
                },
                "required": ["code"],
            },
            final=True,
        )

    def execute(self, args: dict) -> dict:
        code = args.get("code", "").strip()
        if not code:
            return {"text": "代码为空", "files": []}

        timeout = min(int(args.get("timeout", 30)), 120)
        os.makedirs(_TEMP_DIR, exist_ok=True)

        # 写临时 .py 文件
        script_path = os.path.join(_TEMP_DIR, f"_run_{os.urandom(4).hex()}.py")
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            # 执行（cwd=_TEMP_DIR，所以只传文件名）
            logger.info("执行 Python 脚本: %s", script_path)
            result = subprocess.run(
                [sys.executable, os.path.basename(script_path)],
                capture_output=True, text=True, timeout=timeout,
                cwd=_TEMP_DIR,  # 工作目录设为 TEMP_DIR
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            returncode = result.returncode

            # 收集执行后在 TEMP_DIR 生成的文件（递归子目录，排除 .py 脚本自身）
            # 注意：脚本 cwd 就是 TEMP_DIR，且 TEMP_DIR 也传给子进程环境变量，
            # 脚本可能用相对路径写文件，也可能用 os.path.join(TEMP_DIR, f) 多嵌套一层，
            # 两种写法都要能收集到。
            generated = []
            script_mtime = os.path.getmtime(script_path)
            for root, dirs, files in os.walk(_TEMP_DIR):
                dirs[:] = [d for d in dirs if not d.startswith("_run_")]
                for fname in files:
                    fpath = os.path.join(root, fname)
                    if fname.startswith("_run_") or fname == os.path.basename(script_path):
                        continue
                    if os.path.getmtime(fpath) >= script_mtime:
                        generated.append(fpath)

            # 组装回复
            parts = []
            if returncode != 0:
                parts.append(f"退出码: {returncode}")
            if stdout:
                parts.append(stdout[:2000])
            if stderr:
                parts.append(f"【错误】\n{stderr[:1000]}")

            reply = "\n\n".join(parts) if parts else "（无输出）"
            logger.info("脚本执行完成，退出码=%d, 生成 %d 个文件", returncode, len(generated))

            return {"text": reply, "files": generated}

        except subprocess.TimeoutExpired:
            return {"text": f"执行超时（{timeout}秒）", "files": []}
        except Exception as e:
            logger.error("执行脚本异常: %s", e, exc_info=True)
            return {"text": f"执行失败: {e}", "files": []}
        finally:
            # 清理脚本文件
            try:
                if os.path.exists(script_path):
                    os.remove(script_path)
            except Exception:
                pass


registry.register(RunPythonTool())
