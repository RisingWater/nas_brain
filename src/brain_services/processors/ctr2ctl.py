"""CTR 授权转换处理器 — 把微信文件消息里的 .ctr 转成 .ctl 并发送回去

支持两种输入：
    1. 单个 .ctr 文件                      → 回传单个 .ctl
    2. 含 .ctr 的 .zip 包（可多层子目录）  → 全部转换后打包成一个 .zip 回传

存档（默认 data/ctr2ctl/，可用 CTR2CTL_DATA_DIR 覆盖）：
    ctr/     原始 .ctr（单文件用 <request_id>.ctr，zip 内文件保留包内相对路径）
    ctl/     生成的 .ctl（保留包内相对路径）
    records.json   制作记录（一次请求一条）

记录字段：
    time / request_id / protocol / chat_type / sender / chat_name / user_id /
    source（文件名）/ kind（ctr|zip）/ ctr_files[] / ctl_files[] /
    results[{name, ctl, success, error, size, sha256}] / success_count / fail_count /
    zip_reply / base_dir

⚠️ 临时目录**不在这里清理**：返回的 {"files": [...]} 由 user_processor._deliver
   发送到微信后才 os.remove（见 src/brain_services/user_processor.py）。
   在这里 rmtree 会导致发送前文件就没了。
"""
import hashlib
import io
import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile

from . import BaseProcessor, registry
from src.common.schemas.agent_request import AgentRequest, ContentType

logger = logging.getLogger(__name__)

# 子进程超时（秒）
TOOL_TIMEOUT = 60
# 仅支持的源扩展名
SOURCE_EXT = ".ctr"
TARGET_EXT = ".ctl"

# zip 安全限制
_ZIP_MAX_MEMBERS = 200      # 最多解压条目数
_ZIP_MAX_TOTAL = 200 * 1024 * 1024   # 解压后总大小上限 200MB

# 记录文件写入锁（多用户处理线程并发）
_records_lock = threading.Lock()


def _data_dir() -> str:
    """存档根目录（运行时读环境变量，便于容器内改配置）"""
    return os.getenv("CTR2CTL_DATA_DIR", "data/ctr2ctl")


def _ctr_dir() -> str:
    return os.path.join(_data_dir(), "ctr")


def _ctl_dir() -> str:
    return os.path.join(_data_dir(), "ctl")


def _records_file() -> str:
    return os.path.join(_data_dir(), "records.json")


def _ensure_dirs():
    for d in (_data_dir(), _ctr_dir(), _ctl_dir()):
        os.makedirs(d, exist_ok=True)


def _file_ext(name: str) -> str:
    return os.path.splitext(name or "")[1].lower()


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_zip(file_name: str, data: bytes) -> bool:
    """文件名叫 .zip，或内容以 PK 魔数开头"""
    if _file_ext(file_name) == ".zip":
        return True
    return bool(data) and data[:2] == b"PK"


def _winpath(name: str) -> str:
    """统一分隔符并去掉盘符（用于安全检查）"""
    name = (name or "").replace("\\", "/")
    if ":" in name.split("/")[0]:
        name = name.split(":", 1)[-1]
    return name


def _is_unsafe_path(name: str) -> bool:
    """判断 zip 条目是否为危险路径（绝对路径 / 含 .. 逃逸）"""
    normalized = _winpath(name)
    if normalized.startswith("/"):
        return True
    return ".." in normalized.split("/")


def _safe_rel_path(name: str) -> str:
    """把 zip 条目名规整成安全的相对路径

    - 反斜杠转正斜杠、去掉盘符
    - 丢弃空段、"." 和 ".."
    - 返回 '' 表示该条目不可用

    注意：这是「规范化」而非「安全判定」——'../../../x' 会被规范化成 'x'
    （仍落在解压目录内，但属于可疑输入）。是否危险请用 _is_unsafe_path。
    """
    normalized = _winpath(name)
    parts = [p for p in normalized.split("/") if p and p not in (".", "..")]
    return "/".join(parts)


def _unique_path(directory: str, rel_path: str) -> str:
    """在 directory 下为 rel_path 找一个不冲突的落盘路径（重名加 -1/-2）

    会创建父目录，因此调用方拿到路径即可直接写入。
    """
    rel_path = _safe_rel_path(rel_path) or "unnamed"
    candidate = os.path.join(directory, rel_path)
    if _usable(candidate):
        return candidate
    stem, ext = os.path.splitext(rel_path)
    for i in range(1, 1000):
        candidate = os.path.join(directory, f"{stem}-{i}{ext}")
        if _usable(candidate):
            return candidate
    candidate = os.path.join(directory, f"{stem}-{int(time.time())}{ext}")
    os.makedirs(os.path.dirname(candidate) or ".", exist_ok=True)
    return candidate


def _usable(candidate: str) -> bool:
    """路径不存在时创建父目录并返回 True；已存在返回 False"""
    if os.path.exists(candidate):
        return False
    try:
        os.makedirs(os.path.dirname(candidate) or ".", exist_ok=True)
    except Exception:
        return False
    return True


def _convert(input_path: str, output_path: str) -> tuple[bool, str]:
    """调用 ctr2ctl 工具转换，返回 (是否成功, 错误说明)"""
    tool = os.getenv("CTR2CTL_PATH", "/workdir/ctr2ctl")
    cmd = [tool, "--input", input_path, "--output", output_path]
    logger.info("执行转换命令: %s", " ".join(cmd))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=TOOL_TIMEOUT)
    except subprocess.TimeoutExpired:
        logger.error("转换超时: %s", input_path)
        return False, f"转换超时（{TOOL_TIMEOUT}秒）"
    except FileNotFoundError:
        logger.error("转换工具不存在: %s", tool)
        return False, f"转换工具不存在: {tool}"
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


def _convert_one(ctr_path: str, ctl_path: str) -> tuple[bool, str]:
    """转换并校验产物（工具返回 0 也可能没写出文件）"""
    os.makedirs(os.path.dirname(ctl_path) or ".", exist_ok=True)
    ok, err = _convert(ctr_path, ctl_path)
    if not ok:
        return False, err
    if not os.path.exists(ctl_path):
        return False, "转换后的文件未生成"
    if os.path.getsize(ctl_path) == 0:
        return False, "转换后的文件为空"
    return True, ""


def _extract_and_convert(data: bytes, base_name: str = "result",
                         tmpdir: str = None) -> dict:
    """zip 全流程：解压 → 逐个转换 → 打包所有 .ctl（保留包内目录结构）

    不依赖 req / ctx，便于单测与 CLI。返回 outcome dict：
        ctr_files / ctl_files / results / files / reply / zip_reply / fail_count

    归档 ctr 与 ctl 到存档目录（保留包内相对路径）。
    """
    tmpdir = tmpdir or tempfile.mkdtemp()
    extract_dir = os.path.join(tmpdir, "extracted")
    out_dir = os.path.join(tmpdir, "out")
    os.makedirs(extract_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    ctr_entries = []   # [(rel_path, abs_path)]
    total = 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            members = zf.infolist()
            if len(members) > _ZIP_MAX_MEMBERS:
                return _zip_error(f"zip 内文件过多（{len(members)} 个，上限 {_ZIP_MAX_MEMBERS}）")

            # 先整体校验条目路径安全性，有不安全条目就拒收整个包（不静默丢弃）
            for info in members:
                if info.is_dir():
                    continue
                if _is_unsafe_path(info.filename) or not _safe_rel_path(info.filename):
                    return _zip_error(f"zip 内含不安全路径条目: {info.filename!r}")
                if _file_ext(_safe_rel_path(info.filename)) != SOURCE_EXT:
                    continue
                target = os.path.abspath(os.path.join(extract_dir, _safe_rel_path(info.filename)))
                if not target.startswith(os.path.abspath(extract_dir) + os.sep):
                    return _zip_error(f"zip 内含越界条目: {info.filename!r}")

            for info in members:
                if info.is_dir():
                    continue
                rel = _safe_rel_path(info.filename)
                if _file_ext(rel) != SOURCE_EXT:
                    continue
                # 解压大小保护
                total += info.file_size
                if total > _ZIP_MAX_TOTAL:
                    return _zip_error(f"zip 解压后过大（上限 {_ZIP_MAX_TOTAL // 1024 // 1024}MB）")
                try:
                    member_data = zf.read(info)
                except Exception as e:
                    logger.error("读取 zip 条目失败 %s: %s", rel, e)
                    continue

                # 路径安全性已在上面的预校验中确认，这里直接落盘
                target = os.path.join(extract_dir, rel)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as f:
                    f.write(member_data)
                ctr_entries.append((rel, target))
    except zipfile.BadZipFile:
        return _zip_error("zip 文件损坏或格式不正确")
    except Exception as e:
        logger.error("解压 zip 异常: %s", e, exc_info=True)
        return _zip_error(f"解压失败: {e}")

    if not ctr_entries:
        return _zip_error("zip 内没有找到 .ctr 文件")

    logger.info("zip 内找到 %d 个 .ctr 文件", len(ctr_entries))
    _ensure_dirs()

    results = []
    produced = []      # [(rel_ctl, abs_ctl)]
    for rel, abs_ctr in ctr_entries:
        rel_ctl = os.path.splitext(rel)[0] + TARGET_EXT
        abs_ctl = os.path.join(out_dir, rel_ctl)
        ok, err = _convert_one(abs_ctr, abs_ctl)

        # 存档 ctr（保留 zip 内相对路径）
        try:
            shutil.copy2(abs_ctr, _unique_path(_ctr_dir(), rel))
        except Exception as e:
            logger.warning("存档 ctr 失败 %s: %s", rel, e)

        if ok:
            produced.append((rel_ctl, abs_ctl))
            try:
                shutil.copy2(abs_ctl, _unique_path(_ctl_dir(), rel_ctl))
            except Exception as e:
                logger.warning("存档 ctl 失败 %s: %s", rel_ctl, e)

        results.append({
            "name": rel,
            "ctl": rel_ctl,
            "success": ok,
            "error": "" if ok else err,
            "size": os.path.getsize(abs_ctl) if ok else 0,
            "sha256": _sha256(abs_ctl) if ok else "",
        })

    ok_count = len(produced)
    fail_count = len(results) - ok_count
    ctr_files = [rel for rel, _ in ctr_entries]

    if ok_count == 0:
        outcome = _zip_error("zip 内所有 .ctr 文件都转换失败")
        outcome["results"] = results
        outcome["ctr_files"] = ctr_files
        outcome["fail_count"] = fail_count
        return outcome

    # 打包所有 ctl（保留 zip 内目录结构）
    out_zip = os.path.join(tmpdir, f"{base_name}{TARGET_EXT}.zip")
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_ctl, abs_ctl in produced:
            zf.write(abs_ctl, rel_ctl)

    zip_name = os.path.basename(out_zip)
    if fail_count:
        reply = (f"共 {len(results)} 个 .ctr，成功 {ok_count} 个、失败 {fail_count} 个，"
                 f"正在发送 {zip_name}")
    else:
        reply = f"{ok_count} 个文件转换成功，正在发送 {zip_name}"

    logger.info("zip 处理完成：成功 %d，失败 %d，产物 %s", ok_count, fail_count, out_zip)

    # 清理解压/转换中间目录（产物 zip 保留给发送方），避免临时目录堆积
    for _d in (extract_dir, out_dir):
        shutil.rmtree(_d, ignore_errors=True)

    return {
        "ctr_files": ctr_files,
        "ctl_files": [rel for rel, _ in produced],
        "results": results,
        "files": [out_zip],
        "reply": reply,
        "zip_reply": zip_name,
        "fail_count": fail_count,
    }


def _zip_error(error: str) -> dict:
    return {
        "ctr_files": [], "ctl_files": [], "results": [], "files": [],
        "reply": f"转换失败: {error}", "zip_reply": "", "fail_count": 0,
        "error": error,
    }


def _error_outcome(reply: str) -> dict:
    """构造一个「没有任何产物」的 outcome（用于提前失败，仍会写记录）"""
    return {
        "ctr_files": [], "ctl_files": [], "results": [], "files": [],
        "reply": reply, "zip_reply": "", "fail_count": 0, "error": reply,
    }


def _append_record(record: dict):
    """把一条记录追加到 records.json（读-改-写 + 锁）"""
    _ensure_dirs()
    path = _records_file()
    with _records_lock:
        records = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                if not isinstance(records, list):
                    records = []
            except Exception as e:
                logger.error("records.json 解析失败，将重建（旧文件备份为 .bak）: %s", e)
                try:
                    shutil.copy2(path, path + ".bak")
                except Exception:
                    pass
                records = []
        records.append(record)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


class Ctr2CtlProcessor(BaseProcessor):
    name = "ctr2ctl"
    description = "CTR 授权转换处理器（.ctr → .ctl，支持 zip 批量）"

    def priority(self) -> int:
        return 10

    def can_handle(self, req: AgentRequest) -> bool:
        # 只处理文件消息
        if req.content_type != ContentType.FILE or not req.file_id:
            return False
        ext = _file_ext((req.metadata or {}).get("file_name"))
        # 扩展名匹配 .ctr / .zip；无扩展名也放行（可能是不带后缀的 ctr）
        return ext in (SOURCE_EXT, ".zip") or ext == ""

    def handle(self, req: AgentRequest, ctx) -> dict | None:
        meta = req.metadata or {}
        file_name = os.path.basename(meta.get("file_name") or "") or f"input{SOURCE_EXT}"
        ext = _file_ext(file_name)
        kind = "zip" if ext == ".zip" else "ctr"

        if ext not in (SOURCE_EXT, ".zip", ""):
            reply = f"不支持的文件格式 '{ext}'，仅支持 {SOURCE_EXT} 或 .zip"
            ctx.reply(reply)
            self._write_record(req, file_name, "unsupported", _error_outcome(reply))
            return {"reply": reply}

        file_data = ctx.download_file(req.file_id)
        if not file_data:
            ctx.reply("文件下载失败")
            self._write_record(req, file_name, kind, _error_outcome("文件下载失败"))
            return {"reply": "文件下载失败"}

        # 内容嗅探优先于扩展名（.zip 改名的情况也能正确处理）
        kind = "zip" if _is_zip(file_name, file_data) else "ctr"

        # 注意：本目录不清理，交付后由 user_processor 删除产物
        tmpdir = tempfile.mkdtemp()
        _ensure_dirs()

        try:
            if kind == "zip":
                outcome = self._handle_zip(req, ctx, file_data, file_name, tmpdir)
            else:
                outcome = self._handle_single(req, ctx, file_data, file_name, tmpdir)
        except Exception as e:
            logger.error("ctr2ctl 处理异常: %s", e, exc_info=True)
            reply = f"处理失败: {e}"
            ctx.reply(reply)
            self._write_record(req, file_name, kind, _error_outcome(reply))
            return {"reply": reply}

        self._write_record(req, file_name, kind, outcome)

        # 失败明细用第二条消息发（engine 只透传 reply/files，发不了多条）
        failed = [r for r in outcome["results"] if not r["success"]]
        if failed and outcome["files"]:
            who = meta.get("wechat_name", "")
            lines = "\n".join(f"• {r['name']}：{r['error']}" for r in failed[:10])
            more = f"\n（共 {len(failed)} 个失败，此处只列前 10 个）" if len(failed) > 10 else ""
            if who:
                ctx.send_wechat(who, f"以下文件转换失败：\n{lines}{more}")

        ctx.reply(outcome["reply"])
        result = {"reply": outcome["reply"]}
        # 只有真有产物时才带 files（空列表会让 engine 下发空的 files 字段）
        if outcome["files"]:
            result["files"] = outcome["files"]
        return result

    # ---- 单文件 ----

    def _handle_single(self, req, ctx, file_data: bytes, file_name: str, tmpdir: str) -> dict:
        """单个 .ctr：转换后回传单个 .ctl"""
        _ensure_dirs()
        ctr_path = os.path.join(tmpdir, file_name)
        with open(ctr_path, "wb") as f:
            f.write(file_data)

        # 存档原始 ctr（用 request_id 命名，避免同名覆盖）
        archived_ctr = _unique_path(_ctr_dir(), f"{req.request_id}_{file_name}")
        shutil.copy2(ctr_path, archived_ctr)

        ctl_name = os.path.splitext(file_name)[0] + TARGET_EXT
        ctl_path = os.path.join(tmpdir, ctl_name)
        ok, err = _convert_one(ctr_path, ctl_path)

        result = {
            "name": file_name,
            "ctl": ctl_name,
            "success": ok,
            "error": "" if ok else err,
            "size": os.path.getsize(ctl_path) if ok else 0,
            "sha256": _sha256(ctl_path) if ok else "",
        }
        outcome = {
            "ctr_files": [file_name],
            "ctl_files": [ctl_name] if ok else [],
            "results": [result],
            "files": [],
            "reply": "",
            "zip_reply": "",
        }

        if not ok:
            outcome["reply"] = f"文件转换失败: {err}"
            return outcome

        archived_ctl = _unique_path(_ctl_dir(), f"{req.request_id}_{ctl_name}")
        shutil.copy2(ctl_path, archived_ctl)

        outcome["files"] = [ctl_path]
        outcome["reply"] = f"文件转换成功，正在发送 {ctl_name}"
        return outcome

    # ---- zip ----

    def _handle_zip(self, req, ctx, data: bytes, zip_name: str, tmpdir: str) -> dict:
        """含 .ctr 的 zip：交给模块级 _extract_and_convert（解压→转换→打包）"""
        base = os.path.splitext(os.path.basename(zip_name))[0] or "result"
        return _extract_and_convert(data, base_name=base, tmpdir=tmpdir)

    # ---- 记录 ----

    def _write_record(self, req: AgentRequest, file_name: str, kind: str, outcome: dict):
        """把一次请求写成一条记录（失败不影响主流程）"""
        meta = req.metadata or {}
        results = outcome.get("results", [])
        ok_count = sum(1 for r in results if r["success"])
        record = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "request_id": req.request_id,
            "protocol": req.protocol.value if req.protocol else "",
            "chat_type": req.chat_type.value if req.chat_type else "",
            "sender": meta.get("sender") or meta.get("wechat_name", ""),
            "chat_name": meta.get("wechat_name", ""),
            "user_id": req.user_id,
            "source": file_name,
            "kind": kind,
            "ctr_files": outcome.get("ctr_files", []),
            "ctl_files": outcome.get("ctl_files", []),
            "results": results,
            "success_count": ok_count,
            "fail_count": outcome.get("fail_count", len(results) - ok_count),
            "zip_reply": outcome.get("zip_reply", ""),
            "base_dir": _data_dir(),
        }
        try:
            _append_record(record)
            logger.info(
                "制作记录已写入: %s %s 成功 %d/%d",
                record["sender"], file_name, ok_count, len(results),
            )
        except Exception as e:
            logger.error("写制作记录失败: %s", e, exc_info=True)


registry.register(Ctr2CtlProcessor())


if __name__ == "__main__":
    # 本地测试入口（只测转换本身，不经过微信链路）：
    #   python -m src.brain_services.processors.ctr2ctl <文件.ctr> [输出目录]
    #   python -m src.brain_services.processors.ctr2ctl <包.zip>  [输出目录]
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if len(sys.argv) < 2:
        print("用法: python -m src.brain_services.processors.ctr2ctl <文件.ctr|包.zip> [输出目录]")
        sys.exit(1)

    _src = sys.argv[1]
    _outdir = sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp()

    if _is_zip(os.path.basename(_src), open(_src, "rb").read()):
        with open(_src, "rb") as _f:
            _data = _f.read()
        _outcome = _extract_and_convert(_data)
        print(json.dumps({k: v for k, v in _outcome.items() if k != "files"},
                         ensure_ascii=False, indent=2))
        print("产物:", _outcome["files"])
        sys.exit(0 if _outcome["files"] else 1)

    _dst = os.path.join(_outdir, os.path.splitext(os.path.basename(_src))[0] + TARGET_EXT)
    _ok, _err = _convert_one(_src, _dst)
    if _ok:
        print(f"✓ 转换成功: {_dst} ({os.path.getsize(_dst)} 字节)")
        sys.exit(0)
    print(f"✗ 转换失败: {_err}")
    sys.exit(1)
