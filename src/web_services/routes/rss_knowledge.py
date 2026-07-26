"""web_services — RSS 知识查询（读取本地 JSON 文件）"""
import json
import os
import glob
import logging
from fastapi import APIRouter, Query
from typing import Optional

logger = logging.getLogger("web_services.rss_knowledge")

router = APIRouter()

_RSS_DIR = os.getenv("RSS_NEWS_DIR", "data/rss_news")


@router.get("/rss-knowledge")
def get_rss_knowledge(
    tag: Optional[str] = Query(None, description="标签筛选: 股市财经/时政要闻"),
    feed: Optional[str] = Query(None, description="订阅源名称筛选"),
    limit: int = Query(100, ge=1, le=500, description="最多返回条数"),
    offset: int = Query(0, ge=0, description="分页偏移"),
):
    """获取 RSS 知识库内容，按时间倒序"""
    all_items = []
    tag_dirs = [os.path.join(_RSS_DIR, d) for d in os.listdir(_RSS_DIR)
                if os.path.isdir(os.path.join(_RSS_DIR, d))]

    if tag:
        tag_dirs = [d for d in tag_dirs if os.path.basename(d) == tag]

    for tag_dir in tag_dirs:
        tag_name = os.path.basename(tag_dir)
        for fp in sorted(glob.glob(os.path.join(tag_dir, "*.json")), reverse=True):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    items = json.load(f)
                for item in items:
                    item["_tag"] = tag_name
                    if feed and item.get("feed_name") != feed:
                        continue
                    all_items.append(item)
            except Exception as e:
                logger.warning("读取 %s 失败: %s", fp, e)

    # 按 pubDate 倒序（无 pubDate 的放最后）
    def _sort_key(item):
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(item.get("pubDate", "")) or datetime.min
        except Exception:
            return datetime.min

    from datetime import datetime as _dt
    all_items.sort(key=_sort_key, reverse=True)

    total = len(all_items)
    page = all_items[offset:offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": page,
    }


@router.get("/rss-knowledge/feeds")
def get_rss_feeds():
    """获取所有订阅源名称列表"""
    feeds = set()
    tag_dirs = [os.path.join(_RSS_DIR, d) for d in os.listdir(_RSS_DIR)
                if os.path.isdir(os.path.join(_RSS_DIR, d))]
    for tag_dir in tag_dirs:
        for fp in glob.glob(os.path.join(tag_dir, "*.json")):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    items = json.load(f)
                for item in items:
                    if item.get("feed_name"):
                        feeds.add(item["feed_name"])
            except Exception:
                pass
    return {"feeds": sorted(feeds)}


@router.get("/rss-knowledge/tags")
def get_rss_tags():
    """获取所有标签"""
    tags = []
    if os.path.isdir(_RSS_DIR):
        tags = [d for d in os.listdir(_RSS_DIR) if os.path.isdir(os.path.join(_RSS_DIR, d))]
    return {"tags": sorted(tags)}
