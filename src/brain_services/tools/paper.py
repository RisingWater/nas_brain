"""试卷库工具 — 查找/筛选/下载/上传试卷（对接 doc_manager API）"""
import os
import logging
from urllib.parse import unquote

import requests

from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.paper")

_TEMP_DIR = os.path.normpath(os.getenv("TEMP_DIR", "data"))

_PAGE_SIZE = 10  # 搜索每页数量（控制上下文长度）


def _base_url() -> str:
    return os.getenv("DOC_MANAGER_URL", "http://127.0.0.1:8000").rstrip("/")


def _as_list(value) -> list[str]:
    """参数归一化：字符串/数组 → 非空字符串数组"""
    if value is None:
        return []
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value)]


def _safe_path(filename: str) -> str:
    """确保文件路径在 TEMP_DIR 内，防止路径穿越"""
    os.makedirs(_TEMP_DIR, exist_ok=True)
    full = os.path.normpath(os.path.join(_TEMP_DIR, os.path.basename(filename)))
    if not full.startswith(_TEMP_DIR):
        raise ValueError("不允许访问 TEMP_DIR 以外的文件")
    return full


def _filename_from_disposition(header: str, fallback: str) -> str:
    """解析 Content-Disposition 文件名（RFC 5987 filename* 优先）"""
    if header:
        for part in header.split(";"):
            part = part.strip()
            if part.lower().startswith("filename*="):
                try:
                    value = part.partition("=")[2].strip().strip('"')
                    if "'" in value:  # charset'lang'percent-encoded
                        _, _, encoded = value.split("'", 2)
                        value = encoded
                    return os.path.basename(unquote(value))
                except Exception:
                    continue
        for part in header.split(";"):
            part = part.strip()
            if part.lower().startswith("filename="):
                name = part.partition("=")[2].strip().strip('"')
                if name:
                    return os.path.basename(name)
    return fallback


def _format_items(items: list[dict]) -> list[str]:
    """试卷列表 → 文本行（[ID] 文件名（年/科/市/考试/类型））"""
    lines = []
    for it in items:
        dims = "/".join(str(it.get(k) or "-") for k in
                        ("year", "subject", "city", "exam", "paper_type"))
        lines.append(f"[{it.get('id')}] {it.get('file_name', '')}（{dims}）")
    return lines


def _options_hint() -> str:
    """获取库里现有筛选取值，作为空结果的提示（失败返回空串）"""
    try:
        resp = requests.get(f"{_base_url()}/api/meta/options", timeout=10)
        resp.raise_for_status()
        data = resp.json()

        def top(key: str, n: int = 8) -> str:
            vals = [str(o.get("value")) for o in (data.get(key) or [])[:n]]
            return "、".join(vals) if vals else "（无）"

        return ("当前试卷库可选值 — "
                f"年份: {top('years')}；科目: {top('subjects')}；"
                f"地市: {top('cities')}；考试: {top('exams')}；"
                f"类型: {top('paper_types', 3)}")
    except Exception as e:
        logger.debug("获取筛选项失败: %s", e)
        return ""


class SearchPapersTool(BaseTool):
    """按条件查找/筛选试卷"""

    def __init__(self):
        super().__init__(
            name="search_papers",
            display_name="查找试卷",
            description=(
                "在试卷库中按条件查找/筛选试卷。必须至少提供两个筛选条件"
                "（如 地市+科目、年份+科目、考试+科目），单条件结果太多会被拒绝。"
                "支持按年份、科目、地市、考试名称、试卷类型（试卷/答案/试卷+答案）"
                "组合筛选，也可用关键字模糊搜索，返回匹配的试卷列表"
                "（含ID、文件名和分类信息）。找到后可用 download_paper 把文件发给用户。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "years": {
                        "type": "array", "items": {"type": "string"},
                        "description": "年份列表，如 ['2023','2024']",
                    },
                    "subjects": {
                        "type": "array", "items": {"type": "string"},
                        "description": "科目列表，如 ['数学']",
                    },
                    "cities": {
                        "type": "array", "items": {"type": "string"},
                        "description": "地市列表，如 ['福州市']",
                    },
                    "exams": {
                        "type": "array", "items": {"type": "string"},
                        "description": "考试列表，如 ['一检','中考']",
                    },
                    "paper_type": {
                        "type": "array", "items": {"type": "string"},
                        "description": "试卷类型列表，可选值：试卷/答案/试卷+答案",
                    },
                    "q": {
                        "type": "string",
                        "description": "模糊搜索关键字，匹配文件名/路径/所有分类字段",
                    },
                    "page": {
                        "type": "integer",
                        "description": "页码，默认 1（每页 10 条）",
                    },
                },
                "required": [],
            },
        )

    def execute(self, args: dict) -> dict:
        # 至少两个筛选维度（years/subjects/cities/exams/paper_type/q 计数），防止单条件结果过多
        filled = [key for key in ("years", "subjects", "cities", "exams", "paper_type")
                  if _as_list(args.get(key))]
        q = str(args.get("q", "")).strip()
        if len(filled) + (1 if q else 0) < 2:
            hint = _options_hint()
            text = ("筛选条件不足：请至少给两个条件"
                    "（如 地市+科目、年份+科目、考试+科目），单筛一个维度结果太多")
            if hint:
                text += f"。{hint}"
            return {"text": text, "files": []}

        params: dict = {"page_size": _PAGE_SIZE}
        for key in ("years", "subjects", "cities", "exams", "paper_type"):
            values = _as_list(args.get(key))
            if values:
                params[key] = ",".join(values)
        if q:
            params["q"] = q
        params["page"] = str(args.get("page") or 1)

        try:
            resp = requests.get(f"{_base_url()}/api/documents",
                                params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("查找试卷失败: %s", e)
            return {"text": f"查找试卷失败: {e}", "files": []}

        total = data.get("total", 0)
        items = data.get("items", [])
        if not items:
            hint = _options_hint()
            text = "没有找到符合条件的试卷"
            if hint:
                text += f"。{hint}"
            return {"text": text, "files": []}

        page = params["page"]
        lines = [f"共找到 {total} 份试卷（第 {page} 页，每页 {_PAGE_SIZE} 份）："]
        lines += _format_items(items)
        pages = (total + _PAGE_SIZE - 1) // _PAGE_SIZE
        if pages > int(page):
            lines.append(f"（共 {pages} 页，可传 page 参数查看更多）")
        return {"text": "\n".join(lines), "files": []}


class DownloadPaperTool(BaseTool):
    """按 ID 批量下载试卷文件并发送"""

    _MAX = 10  # 单次最多下载份数

    def __init__(self):
        super().__init__(
            name="download_paper",
            display_name="下载试卷",
            description=(
                "按 ID 下载试卷文件并发送给用户，支持一次传多个 ID 批量下载（最多 10 份）。"
                "ID 需先通过 search_papers 查询获得（列表中每项的 [ID]）。"
                "用户想要试卷文件时调用此工具。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "试卷 ID 列表（search_papers 结果中的 [ID]），如 [12, 15]",
                    },
                },
                "required": ["ids"],
            },
        )

    def execute(self, args: dict) -> dict:
        raw = args.get("ids")
        if raw is None:
            raw = args.get("id")  # 兼容旧单 ID 参数
        if raw is None:
            return {"text": "请提供试卷 ID（先用 search_papers 查找）", "files": []}
        if isinstance(raw, (int, str)):
            raw = [raw]

        ids = []
        for v in raw:
            try:
                pid = int(str(v).strip())
            except (ValueError, TypeError):
                continue
            if pid > 0:
                ids.append(pid)
        ids = list(dict.fromkeys(ids))[:self._MAX]
        if not ids:
            return {"text": "请提供试卷 ID（先用 search_papers 查找）", "files": []}

        files = []
        ok_names = []
        errors = []
        for paper_id in ids:
            try:
                resp = requests.get(
                    f"{_base_url()}/api/documents/{paper_id}/download",
                    stream=True, timeout=120)
                if resp.status_code == 404:
                    errors.append(f"试卷 {paper_id} 不存在或文件已被删除")
                    continue
                resp.raise_for_status()
                filename = _filename_from_disposition(
                    resp.headers.get("Content-Disposition", ""),
                    f"paper_{paper_id}.pdf")
                filepath = _safe_path(filename)
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=64 * 1024):
                        if chunk:
                            f.write(chunk)
                logger.info("试卷已下载: id=%s -> %s (%.1f KB)",
                            paper_id, filepath, os.path.getsize(filepath) / 1024)
                files.append(filepath)
                ok_names.append(filename)
            except requests.RequestException as e:
                logger.error("下载试卷失败: id=%s, %s", paper_id, e)
                errors.append(f"试卷 {paper_id} 下载失败")

        parts = []
        if files:
            parts.append(f"已下载 {len(files)} 份：{'、'.join(ok_names)}")
        if errors:
            parts.append("；".join(errors))
        text = "\n".join(parts) if parts else "下载失败"
        return {"text": text, "files": files}


class UploadPaperTool(BaseTool):
    """上传试卷文件到试卷库"""

    def __init__(self):
        super().__init__(
            name="upload_paper",
            display_name="上传试卷",
            description=(
                "把临时目录中的文件上传到试卷库。filepath 为临时目录里已存在的文件名"
                "（如刚生成的 PDF/试卷文件），可附年份、科目、地市、考试等分类信息"
                "（均可选，不填的维度不建目录层）。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "临时目录中的文件名，如 '化学卷.pdf'",
                    },
                    "year": {"type": "string", "description": "年份，如 '2026'（可选）"},
                    "subject": {"type": "string", "description": "科目，如 '数学'（可选）"},
                    "city": {"type": "string", "description": "地市，如 '福州市'（可选）"},
                    "exam": {"type": "string", "description": "考试，如 '一检'（可选）"},
                },
                "required": ["filepath"],
            },
            final=True,
        )

    def execute(self, args: dict) -> dict:
        filename = str(args.get("filepath", "")).strip()
        if not filename:
            return {"text": "请提供要上传的文件名（filepath）", "files": []}
        try:
            src = _safe_path(filename)
        except ValueError as e:
            return {"text": str(e), "files": []}
        if not os.path.exists(src):
            return {"text": f"文件不存在：{filename}", "files": []}

        data = {}
        for key in ("year", "subject", "city", "exam"):
            value = str(args.get(key, "")).strip()
            if value:
                data[key] = value

        try:
            with open(src, "rb") as f:
                resp = requests.post(
                    f"{_base_url()}/api/upload",
                    data=data,
                    files={"file": (os.path.basename(src), f)},
                    timeout=120)
            if resp.status_code == 400:
                try:
                    detail = resp.json().get("detail", "参数不合法")
                except Exception:
                    detail = "参数不合法"
                return {"text": f"上传失败：{detail}", "files": []}
            resp.raise_for_status()
            result = resp.json()
            if result.get("ok"):
                logger.info("试卷已上传: %s -> id=%s", src, result.get("id"))
                return {"text": f"已上传到试卷库：{result.get('file_name', filename)}",
                        "files": []}
            return {"text": f"上传失败：{result}", "files": []}
        except requests.RequestException as e:
            logger.error("上传试卷失败: %s", e)
            return {"text": f"上传试卷失败: {e}", "files": []}


registry.register(SearchPapersTool())
registry.register(DownloadPaperTool())
registry.register(UploadPaperTool())
