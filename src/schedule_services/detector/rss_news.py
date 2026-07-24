"""rss_news_detector — RSS 新闻/资讯获取

定时从 RSSHub 获取指定订阅源的最新内容，保存到本地 JSON 文件。
每个源可独立配置拉取时间，按 pubDate 去重。
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

logger = logging.getLogger("schedule_services.detector.rss_news")


class RssFeedItem(BaseModel):
    url: str = Field(..., title="RSS 地址", description="RSSHub 订阅地址")
    name: str = Field(..., title="名称", description="如 股市通、财联社")
    tags: list[Literal["股市财经", "时政要闻"]] = Field(
        default_factory=list, title="标签",
        description="每条内容附加的标签",
    )
    fetch_times: list[str] = Field(
        ["04:00", "16:00"], title="拉取时间",
        description="每天在此时间点拉取，HH:MM 格式，可多个",
    )


_default_feeds = [
    RssFeedItem(url="http://192.168.1.180:1200/baidu/gushitong/index", name="股市通",
                tags=["股市财经"], fetch_times=["04:00", "10:00", "16:00", "22:00"]),
    RssFeedItem(url="http://192.168.1.180:1200/cls/telegraph/watch", name="财联社",
                tags=["股市财经"]),
    RssFeedItem(url="http://192.168.1.180:1200/guancha/headline", name="观察者网",
                tags=["时政要闻"]),
    RssFeedItem(url="http://192.168.1.180:1200/ainvest/news", name="AI投资",
                tags=["股市财经"]),
]


class RssNewsConfig(BaseModel):
    interval: int = Field(
        600, title="运行间隔（秒）", ge=60,
        description="主循环每 10 分钟检查一次是否到拉取时间",
    )
    feeds: list[RssFeedItem] = Field(
        default=_default_feeds, title="订阅源",
        description="要获取的 RSS 订阅地址列表，每个源可独立设置拉取时间",
    )
    output_dir: str = Field(
        "data/rss_news", title="保存目录",
        description="获取的内容保存到此目录，按日期分文件",
    )


class RssNewsDetector(BaseDetector):
    """RSS 资讯获取

    定时从 RSSHub 获取指定订阅源的最新内容，保存到本地。
    每个源独立调度，跟踪最新 pubDate 去重。
    """

    name = "rss_news"
    interval = 600
    ConfigModel = RssNewsConfig

    _state_file: str = "data/detector/rss_news_state.json"

    def __init__(self):
        super().__init__()
        self._feeds: list[dict] = [f.model_dump() for f in _default_feeds]
        self._output_dir = "data/rss_news"
        # 每个源上次执行的日期（同一天不重复触发）
        self._last_check: dict[str, str | None] = {}
        self._state: dict[str, str] = {}  # feed_url → 最新 pubDate 原始字符串

    # ---- 状态持久化（本地 JSON 文件）----

    def _load_state(self):
        try:
            if os.path.exists(self._state_file):
                with open(self._state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._state = data.get("state", {})
                self._last_check = data.get("last_check", {})
        except Exception as e:
            logger.warning("加载状态文件失败: %s", e)
            self._state = {}
            self._last_check = {}

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump({
                    "state": self._state,
                    "last_check": self._last_check,
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("保存状态文件失败: %s", e)

    # ---- 配置加载 ----

    def load_config(self) -> dict:
        cfg = super().load_config()
        self.interval = cfg.get("interval", self.interval)
        self._output_dir = cfg.get("output_dir", self._output_dir)
        saved_feeds = cfg.get("feeds", None)
        if saved_feeds and isinstance(saved_feeds, list):
            self._feeds = saved_feeds
        else:
            self._feeds = [f.model_dump() for f in _default_feeds]
        return cfg

    # ---- 主循环 ----

    def process_loop(self, ctx: DetectorContext):
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        self._load_state()

        for feed in self._feeds:
            try:
                self._check_feed(feed, now, today)
            except Exception as e:
                logger.error("获取 %s 失败: %s", feed.get("name", feed["url"]), e)

    def trigger(self):
        """手动触发：无视拉取时间，立即拉取所有源"""
        from .base import DetectorContext
        self._load_state()
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        for feed in self._feeds:
            self._last_check.pop(feed["url"], None)  # 清日期标记
            try:
                self._check_feed(feed, now, today, force=True)
            except Exception as e:
                logger.error("手动触发 %s 失败: %s", feed.get("name", feed["url"]), e)

    def _check_feed(self, feed: dict, now: datetime, today: str, force: bool = False):
        feed_url = feed["url"]
        feed_name = feed.get("name", feed_url)
        fetch_times = feed.get("fetch_times", ["04:00", "16:00"])

        # 检查当前时间是否匹配该源的拉取时间（手动触发时跳过）
        if not force:
            matched = False
            for t in fetch_times:
                try:
                    parts = t.strip().split(":")
                    if now.hour == int(parts[0]) and now.minute == int(parts[1]):
                        matched = True
                        break
                except Exception:
                    continue
            if not matched:
                return

        # 同一天不重复触发（同一个源一天内多次拉取需要配置多个时间点）
        last_date = self._last_check.get(feed_url)
        if last_date == today:
            return
        self._last_check[feed_url] = today

        # 只记一次 save（减少磁盘写入）
        need_save = False

        logger.info("拉取: %s", feed_name)

        resp = _requests_get(feed_url, timeout=15)
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")

        # 读上次最新时间
        last_pubdate_raw = self._state.get(feed_url, "")
        last_pubdate = _parse_pubdate(last_pubdate_raw) if last_pubdate_raw else None

        new_items = []
        latest_raw = last_pubdate_raw  # 最新一条的原始 pubDate 字符串
        has_pubdate = False

        for item in items:
            title = item.findtext("title", "")
            pubdate_str = item.findtext("pubDate", "") or ""
            link = item.findtext("link", "")
            guid = item.findtext("guid", "") or link
            desc = item.findtext("description", "")

            pubdate = _parse_pubdate(pubdate_str) if pubdate_str else None

            if pubdate:
                has_pubdate = True
                if last_pubdate and pubdate <= last_pubdate:
                    continue
                # 记录最新的原始字符串（不转换格式）
                if not latest_raw or pubdate > _parse_pubdate(latest_raw):
                    latest_raw = pubdate_str

            clean_desc = re.sub(r"<[^>]+>", "", desc).strip()
            feed_tags = feed.get("tags", []) or []

            new_items.append({
                "title": title,
                "pubDate": pubdate_str,
                "link": link,
                "guid": guid,
                "description": clean_desc,
                "tags": feed_tags,
                "feed_name": feed_name,
            })

        if not new_items:
            logger.info("%s: 无新内容", feed_name)
            self._save_state()
            return

        # 保存到文件（按标签分目录）
        feed_tags = feed.get("tags", []) or []
        tag_dir = feed_tags[0] if feed_tags else "其他"
        save_dir = os.path.join(self._output_dir, tag_dir)
        os.makedirs(save_dir, exist_ok=True)
        date_str = now.strftime("%Y%m%d")
        filepath = os.path.join(save_dir, f"{feed_name}_{date_str}.json")

        if has_pubdate:
            existing = []
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    existing = []
            all_items = existing + new_items
        else:
            all_items = new_items

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(all_items, f, ensure_ascii=False, indent=2)

        logger.info("%s: 新增 %d 条，共 %d 条", feed_name, len(new_items), len(all_items))

        # 更新状态
        if latest_raw:
            self._state[feed_url] = latest_raw
        self._save_state()


def _parse_pubdate(s: str) -> datetime | None:
    """解析 RSS pubDate（RFC 2822 格式）"""
    try:
        return parsedate_to_datetime(s)
    except Exception:
        return None


def _requests_get(url: str, timeout: int = 10):
    import requests
    return requests.get(url, timeout=timeout)


registry.register(RssNewsDetector())
