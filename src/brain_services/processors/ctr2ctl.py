"""CTR 授权转换处理器 — 把微信文件消息里的 .ctr 转成 .ctl 并发送回去

只处理文件消息（ContentType.FILE），不处理图片/文本/链接。

流程：
    下载 .ctr → 调用 ctr2ctl 工具 → 校验产物非空 → 返回 files 路径

⚠️ 临时目录**不在这里清理**：返回的 {"files": [...]} 由 user_processor._deliver
   发送到微信后才 os.remove（见 src/brain_services/user_processor.py）。
   在这里 rmtree 会导致发送前文件就没了。

工具路径：默认 /workdir/ctr2ctl，可用环境变量 CTR2CTL_PATH 覆盖。
"""
import logging
import os
import subprocess
import tempfile

from . import BaseProcessor, registry
from src.common.schemas.agent_request import AgentRequest, ContentType

logger = logging.getLogger(__name__)

# 转换工具路径（容器内 /workdir/ctr2ctl，可用环境变量覆盖）
TOOL_PATH = os.getenv("CTR2CTL_PATH", "/workdir/ctr2ctl")
# 子进程超时（秒）
TOOL_TIMEOUT = 60
# 仅支持的源扩展名
SOURCE_EXT = ".ctr"


class Ctr2CtlProcessor(BaseProcessor):
    name = "ctr2ctl"
    description = "CTR 授权转换处理器（.ctr → .ctl）"

    def priority(self) -> int:
        return 10

    def can_handle(self, req: AgentRequest) -> bool:
        # 只处理文件消息
        if req.content_type != ContentType.FILE or not req.file_id:
            return False
        # 扩展名必须匹配，否则交给后面的处理器（如 print）
        return self._source_ext(req) == SOURCE_EXT

    def handle(self, req: AgentRequest, ctx) -> dict | None:
        meta = req.metadata or {}
        file_name = os.path.basename(meta.get("file_name") or "") or f"input{SOURCE_EXT}"
        base_name, ext = os.path.splitext(file_name)

        if ext.lower() != SOURCE_EXT:
            reply = f"不支持的文件格式 '{ext}'，仅支持 {SOURCE_EXT} 文件"
            ctx.reply(reply)
            return {"reply": reply}

        file_data = ctx.download_file(req.file_id)
        if not file_data:
            ctx.reply("文件下载失败")
            return {"reply": "文件下载失败"}

        # 注意：本目录不清理，交付后由 user_processor 删除文件
        tmpdir = tempfile.mkdtemp()
        ctr_path = os.path.join(tmpdir, file_name)
        ctl_name = f"{base_name}.ctl"
        ctl_path = os.path.join(tmpdir, ctl_name)

        with open(ctr_path, "wb") as f:
            f.write(file_data)

        logger.info("CTR 处理器开始转换: %s -> %s", ctr_path, ctl_path)

        ok, error = self._convert(ctr_path, ctl_path)
        if not ok:
            reply = f"文件转换失败: {error}"
            ctx.reply(reply)
            return {"reply": reply}

        # 校验产物
        if not os.path.exists(ctl_path):
            reply = f"转换后的文件未生成: {ctl_name}"
            ctx.reply(reply)
            return {"reply": reply}

        size = os.path.getsize(ctl_path)
        if size == 0:
            reply = f"转换后的文件为空: {ctl_name}"
            ctx.reply(reply)
            return {"reply": reply}

        logger.info("转换成功: %s (%d 字节)", ctl_name, size)
        reply = f"文件转换成功，正在发送 {ctl_name}"
        ctx.reply(reply)
        return {"reply": reply, "files": [ctl_path]}

    @staticmethod
    def _source_ext(req: AgentRequest) -> str:
        """取文件消息的扩展名（小写）"""
        file_name = (req.metadata or {}).get("file_name") or ""
        return os.path.splitext(file_name)[1].lower()

    @staticmethod
    def _convert(input_path: str, output_path: str) -> tuple[bool, str]:
        """调用 ctr2ctl 工具转换，返回 (是否成功, 错误说明)"""
        cmd = [TOOL_PATH, "--input", input_path, "--output", output_path]
        logger.info("执行转换命令: %s", " ".join(cmd))

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=TOOL_TIMEOUT)
        except subprocess.TimeoutExpired:
            logger.error("转换超时: %s", input_path)
            return False, f"转换超时（{TOOL_TIMEOUT}秒）"
        except FileNotFoundError:
            logger.error("转换工具不存在: %s", TOOL_PATH)
            return False, f"转换工具不存在: {TOOL_PATH}"
        except Exception as e:
            logger.error("转换异常: %s", e, exc_info=True)
            return False, str(e)

        if result.returncode == 0:
            if result.stdout:
                logger.info("转换输出: %s", result.stdout.strip())
            return True, ""

        stderr = (result.stderr or "").strip()
        logger.error("转换失败，返回码 %s: %s", result.returncode, stderr)
        return False, stderr or f"工具返回码 {result.returncode}"


registry.register(Ctr2CtlProcessor())


if __name__ == "__main__":
    # 本地测试入口：python -m src.brain_services.processors.ctr2ctl <文件.ctr> [输出目录]
    # 只测转换本身，不经过微信下载/发送链路
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if len(sys.argv) < 2:
        print("用法: python -m src.brain_services.processors.ctr2ctl <文件.ctr> [输出目录]")
        sys.exit(1)

    _src = sys.argv[1]
    _outdir = sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp()
    _dst = os.path.join(_outdir, os.path.splitext(os.path.basename(_src))[0] + ".ctl")
    _ok, _err = Ctr2CtlProcessor._convert(_src, _dst)
    if _ok and os.path.exists(_dst) and os.path.getsize(_dst) > 0:
        print(f"✓ 转换成功: {_dst} ({os.path.getsize(_dst)} 字节)")
        sys.exit(0)
    print(f"✗ 转换失败: {_err}")
    sys.exit(1)
