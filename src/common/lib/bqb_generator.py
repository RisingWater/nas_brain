"""梗图生成器 — 搜索表情包并缓存到本地"""
import os
import re
import random
import logging
import cloudscraper
from urllib.parse import quote

logger = logging.getLogger(__name__)

_BQB_DIR = os.getenv("BQB_DIR", "data/bqb")
_API_BASE = os.getenv("BQB_API_URL", "http://129.211.70.28/api/img/apihzbqb.php")
_API_ID = os.getenv("BQB_API_ID", "10019603")
_API_KEY = os.getenv("BQB_API_KEY", "fca1848ad76ba059f6346c3c601aa624")

_scraper = None


def _get_scraper():
    global _scraper
    if _scraper is None:
        _scraper = cloudscraper.create_scraper()
        _scraper.headers.update({
            "Referer": "https://cn.apihz.cn/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        })
    return _scraper


def _extract_filename(url: str) -> str:
    """从 URL 中提取文件名"""
    return url.rsplit("/", 1)[-1]


def search_bqb(keyword: str, limit: int = 10) -> list[str]:
    """搜索表情包，返回图片 URL 列表"""
    url = f"{_API_BASE}?id={_API_ID}&key={_API_KEY}&type=2&words={quote(keyword)}&limit={limit}"
    scraper = _get_scraper()
    resp = scraper.get(url, timeout=15)
    data = resp.json()
    if data.get("code") != 200:
        logger.warning("BQB API 返回错误: %s", data.get("msg"))
        return []
    return data.get("res", [])


def get_random_bqb(keyword: str) -> str | None:
    """搜索关键字，从前 10 个结果中随机选一张，下载到缓存并返回本地路径

    缓存策略：以 {关键字}_{原始文件名} 为缓存 key。
    同一张图片不会重复下载，但每次调用仍会随机选图。
    """
    urls = search_bqb(keyword, limit=10)
    if not urls:
        logger.warning("未搜索到相关表情包: %s", keyword)
        return None

    safe_kw = re.sub(r'[\\/:*?"<>|]', "_", keyword)
    os.makedirs(_BQB_DIR, exist_ok=True)

    # 随机选一张，缓存命中则跳过下载
    chosen = random.choice(urls)
    filename = _extract_filename(chosen)
    cached = os.path.join(_BQB_DIR, f"{safe_kw}_{filename}")

    if os.path.exists(cached):
        logger.info("BQB 缓存命中: %s", cached)
        return cached

    scraper = _get_scraper()
    resp = scraper.get(chosen, timeout=15)
    if resp.status_code != 200 or "image" not in resp.headers.get("Content-Type", ""):
        logger.warning("BQB 下载失败: %s %s", chosen, resp.status_code)
        return None

    with open(cached, "wb") as f:
        f.write(resp.content)
    logger.info("BQB 已下载: %s", cached)
    return cached
