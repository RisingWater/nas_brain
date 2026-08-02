"""PaddleOCR 客户端 — 调用 PaddleOCR Simple Server"""
import logging
import os
import requests

logger = logging.getLogger(__name__)

_OCR_URL = os.getenv("OCR_SERVER_URL", "http://localhost:3000/recognize")
_OCR_TOKEN = os.getenv("OCR_SERVER_TOKEN", "")


class PaddleOCR:
    """PaddleOCR 文字识别客户端"""

    def __init__(self, url: str = "", token: str = ""):
        self._url = url or _OCR_URL
        self._token = token or _OCR_TOKEN

    def recognize(self, image_path: str) -> dict:
        """识别图片文字，返回 {"success": bool, "text": str, "items": list, "error": str}"""
        if not os.path.exists(image_path):
            return {"success": False, "text": "", "items": [], "error": f"文件不存在: {image_path}"}
        try:
            with open(image_path, "rb") as f:
                headers = {}
                if self._token:
                    headers["Authorization"] = f"Bearer {self._token}"
                resp = requests.post(self._url, files={"img": f}, headers=headers, timeout=30)
            logger.info("PaddleOCR raw: %s %s", resp.status_code, resp.text[:500])
            resp.raise_for_status()
            data = resp.json()
            # PaddleOCR Simple Server 返回: {"text": "...", "lines": [[{"text":"...","confidence":...}]]}
            if "text" in data and data["text"]:
                return {"success": True, "text": data["text"], "items": data.get("lines", []), "error": ""}
            # 兼容其他格式
            items = data.get("data", data.get("result", []))
            if not items:
                return {"success": True, "text": "", "items": [], "error": ""}
            texts = []
            for item in items:
                if isinstance(item, dict):
                    texts.append(item.get("text", str(item)))
                elif isinstance(item, str):
                    texts.append(item)
                else:
                    texts.append(str(item))
            return {"success": True, "text": "\n".join(texts), "items": items, "error": ""}
        except Exception as e:
            logger.error("PaddleOCR 识别失败: %s", e)
            return {"success": False, "text": "", "items": [], "error": str(e)}


# 全局默认实例
_default_ocr = None


def get_ocr() -> PaddleOCR:
    global _default_ocr
    if _default_ocr is None:
        _default_ocr = PaddleOCR()
    return _default_ocr


def ocr_recognize(image_path: str) -> str:
    """便捷函数：直接返回识别文本"""
    result = get_ocr().recognize(image_path)
    return result["text"]


def layout_ocr_text(lines: list, gap_factor: float = 1.15) -> str:
    """按 box 坐标重建版面，生成适合 LLM 阅读的多行文本

    OCR 服务返回的 text 是按识别顺序拼接的纯文本流，丢失版面信息：
    视觉上相距很远的字段（如"下单时间"与车次时刻）在文本里相邻，
    LLM 容易把它们错误组合。此函数用坐标还原布局：

    - 同一视觉行（y 中心接近）的片段按 x 从左到右合并为一行
    - 行距显著超过中位行距（视觉区块边界）时插入空行分隔

    行距用「顶到顶」（top-to-top）而非底到顶：PaddleOCR 的 box 高度
    虚高（含 padding，且不同行差异大），底到顶间距会被严重扭曲；
    顶到顶间距分布更干净，块内行距 vs 块间行距有清晰分层。

    分块阈值自适应：取所有行距的中位数为基线（均匀行距的截图如终端
    日志，所有行距 ≈ 中位数，不会分块；有区块的截图，块间行距显著
    超过中位数）。判定需要同时满足两个条件（防像素级噪声误分）：
    gap > 中位行距 × gap_factor 且 gap > 中位行距 + 3px

    Args:
        lines: PaddleOCR 返回的 lines 字段（嵌套数组）
            [[{"text": "...", "box": {"x","y","width","height"}, "confidence": ...}], ...]
        gap_factor: 区块判定系数（默认 1.15）

    Returns:
        重排后的多行文本；lines 为空时返回 ""
    """
    items = []
    for group in lines or []:
        if isinstance(group, list):
            for it in group:
                if isinstance(it, dict) and it.get("text") and isinstance(it.get("box"), dict):
                    items.append(it)
        elif isinstance(group, dict) and group.get("text") and isinstance(group.get("box"), dict):
            items.append(group)
    if not items:
        return ""

    # 1. y 中心聚类成视觉行（同一行内按 x 排序）
    rows = []
    for it in items:
        box = it["box"]
        x = box.get("x", 0) or 0
        y = box.get("y", 0) or 0
        w = box.get("width", 0) or 0
        h = box.get("height", 0) or 0
        cy = y + h / 2
        # 同行判定：中心差 <= 平均行高 * 0.45。
        # 注意 OCR box 高度偏大（含 padding），相邻视觉行的中心差可能接近行高，
        # 阈值过宽会把多行误并成一行；同一行内片段的中心差通常 < 5px，余量充足
        for row in rows:
            if abs(cy - row["cy"]) <= (row["h"] + h) / 2 * 0.45:
                row["items"].append((x, str(it["text"])))
                row["cy"] = (row["cy"] + cy) / 2
                row["y"] = min(row["y"], y)
                row["h"] = max(row["h"], h)
                break
        else:
            rows.append({"items": [(x, str(it["text"]))], "cy": cy, "y": y, "h": h})

    # 2. 计算顶到顶行距的中位数（自适应当前截图的行距尺度）
    rows.sort(key=lambda r: r["y"])
    gaps = [rows[i]["y"] - rows[i - 1]["y"] for i in range(1, len(rows))]
    gaps.sort()
    median_gap = gaps[len(gaps) // 2] if gaps else 0

    # 3. 自上而下输出，行距显著超过中位数的行视为新视觉区块，用空行分隔
    out = []
    for i, row in enumerate(rows):
        line = " ".join(t for _, t in sorted(row["items"]))
        if i > 0 and median_gap > 0:
            gap = row["y"] - rows[i - 1]["y"]
            if gap > median_gap * gap_factor and gap > median_gap + 3:
                out.append("")
        out.append(line)
    return "\n".join(out)
