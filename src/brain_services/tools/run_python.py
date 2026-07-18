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

            # 收集执行后在 TEMP_DIR 生成的文件（排除 .py 自身）
            generated = []
            for fname in os.listdir(_TEMP_DIR):
                if fname.startswith("_run_") or fname == os.path.basename(script_path):
                    continue
                fpath = os.path.join(_TEMP_DIR, fname)
                if os.path.isfile(fpath) and os.path.getmtime(fpath) >= os.path.getmtime(script_path):
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
