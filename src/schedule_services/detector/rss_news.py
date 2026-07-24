"""rss_news_detector — RSS 新闻/资讯获取

定时从 RSSHub 获取指定订阅源，保存到本地文件，去重。
每 10 分钟运行一次，在指定时间点（如 4:00 / 16:00）拉取新数据。
"""
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, time as dt_time
from email.utils import parsedate_to_datetime
from typing import Literal
from pydantic import BaseModel, Field

from .base import BaseDetector, DetectorContext, registry
from src.common.clients.kv_store import kv_store

logger = logging.getLogger("schedule_services.detector.rss_news")


class RssFeedItem(BaseModel):
    url: str = Field(..., title="RSS 地址", description="RSSHub 订阅地址")
    name: str = Field(..., title="名称", description="如 股市通、财联社")


_default_feeds = [
    RssFeedItem(url="http://192.168.1.180:1200/baidu/gushitong/index", name="股市通"),
    RssFeedItem(url="http://192.168.1.180:1200/cls/telegraph/watch", name="财联社"),
]


class RssNewsConfig(BaseModel):
    interval: int = Field(
        600, title="运行间隔（秒）", ge=60,
        description="主循环每 10 分钟检查一次是否到获取时间",
    )
    fetch_times: list[str] = Field(
        ["04:00", "16:00"], title="获取时间",
        description="每天在此时间点获取 RSS，HH:MM 格式，可多个",
    )
    feeds: list[RssFeedItem] = Field(
        default=_default_feeds, title="订阅源",
        description="要获取的 RSS 订阅地址列表",
    )
    output_dir: str = Field(
        "data/rss_news", title="保存目录",
        description="获取的内容保存到此目录，按日期分文件",
    )


class RssNewsDetector(BaseDetector):
    """RSS 资讯获取

    定时从 RSSHub 获取指定订阅源的最新内容，保存到本地。
    跟踪每个源的最新 pubDate 以去重。
    """

    name = "rss_news"
    interval = 600
    ConfigModel = RssNewsConfig

    def __init__(self):
        super().__init__()
        self._fetch_times: list[dt_time] = [dt_time(4, 0), dt_time(16, 0)]
        self._feeds: list[dict] = [f.model_dump() for f in _default_feeds]
        self._output_dir = "data/rss_news"
        self._last_check_date = None  # 每天第一次触发后不再重复

    def load_config(self) -> dict:
        cfg = super().load_config()
        self.interval = cfg.get("interval", self.interval)
        self._output_dir = cfg.get("output_dir", self._output_dir)
        saved_feeds = cfg.get("feeds", None)
        if saved_feeds and isinstance(saved_feeds, list):
            self._feeds = saved_feeds
        else:
            self._feeds = [f.model_dump() for f in _default_feeds]
        saved_times = cfg.get("fetch_times", None)
        if saved_times and isinstance(saved_times, list):
            self._fetch_times = []
            for t in saved_times:
                try:
                    parts = t.strip().split(":")
                    self._fetch_times.append(dt_time(int(parts[0]), int(parts[1])))
                except Exception:
                    pass
            if not self._fetch_times:
                self._fetch_times = [dt_time(4, 0), dt_time(16, 0)]
        return cfg

    def process_loop(self, ctx: DetectorContext):
        now = datetime.now()

        # 检查是否到指定时间
        now_time = now.time()
        matched = False
        for ft in self._fetch_times:
            if now.hour == ft.hour and now.minute == ft.minute:
                matched = True
                break
        if not matched:
            return

        # 同一天只执行一次（防止同一个小时内重复触发）
        if self._last_check_date == now.date():
            return
        self._last_check_date = now.date()

        logger.info("开始获取 RSS 资讯: %s", now.strftime("%Y-%m-%d %H:%M"))

        for feed in self._feeds:
            try:
                self._fetch_feed(feed, now)
            except Exception as e:
                logger.error("获取 %s 失败: %s", feed.get("name", feed["url"]), e)

    def _fetch_feed(self, feed: dict, now: datetime):
        feed_url = feed["url"]
        feed_name = feed.get("name", feed_url)
        logger.info("获取: %s", feed_name)

        resp = requests_get(feed_url, timeout=15)
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")

        # 从 kv_store 读上次的最新时间
        state_key = f"rss_last_pubdate:{feed_url}"
        last_pubdate_str = kv_store.get(state_key) or ""
        last_pubdate = _parse_pubdate(last_pubdate_str) if last_pubdate_str else None

        new_items = []
        latest_pubdate = last_pubdate
        has_pubdate = False  # 是否有时间戳（新闻）还是纯快照（指数）

        for item in items:
            title = item.findtext("title", "")
            pubdate_str = item.findtext("pubDate", "") or ""
            link = item.findtext("link", "")
            guid = item.findtext("guid", "") or link
            desc = item.findtext("description", "")

            pubdate = _parse_pubdate(pubdate_str) if pubdate_str else None

            if pubdate:
                has_pubdate = True
                # 按时间去重
                if last_pubdate and pubdate <= last_pubdate:
                    continue
                if latest_pubdate is None or pubdate > latest_pubdate:
                    latest_pubdate = pubdate

            # 清理 desc 里 HTML 标签
            clean_desc = re.sub(r"<[^>]+>", "", desc).strip()

            new_items.append({
                "title": title,
                "pubDate": pubdate_str,
                "link": link,
                "guid": guid,
                "description": clean_desc,
            })

        if not new_items:
            logger.info("%s: 无新内容", feed_name)
            return

        # 保存到文件
        os.makedirs(self._output_dir, exist_ok=True)
        date_str = now.strftime("%Y%m%d")
        filepath = os.path.join(self._output_dir, f"{feed_name}_{date_str}.json")

        if has_pubdate:
            # 有时间戳 → 追加到今日文件
            existing = []
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    existing = []
            all_items = existing + new_items
        else:
            # 无时间戳（指数快照）→ 覆盖模式，保留最新
            all_items = new_items

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(all_items, f, ensure_ascii=False, indent=2)

        logger.info("%s: 新增 %d 条，共 %d 条", feed_name, len(new_items), len(all_items))

        # 更新最新时间到 kv_store
        if latest_pubdate:
            kv_store.set(state_key, latest_pubdate.strftime("%Y-%m-%dT%H:%M:%SZ"))


def _parse_pubdate(s: str) -> datetime | None:
    """解析 RSS pubDate"""
    try:
        return parsedate_to_datetime(s)
    except Exception:
        return None


def requests_get(url: str, timeout: int = 10):
    """带超时的 GET 请求"""
    import requests
    return requests.get(url, timeout=timeout)


registry.register(RssNewsDetector())
