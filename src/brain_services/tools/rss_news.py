"""RSS 新闻查询工具 — 读取 data/rss_news 中保存的资讯"""
import json
import logging
import os
from datetime import datetime
from . import BaseTool, registry

logger = logging.getLogger("brain_services.tools.read_news")

_NEWS_DIR = "data/rss_news"


class ReadNewsTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="rss_news",
            display_name="RSS 新闻",
            description=(
                "获取用户已订阅的RSS源最新推送内容。专用于快速获取今日/当下的"
                "时政要闻、政策动向及股市财经快讯。此工具响应极快，是获取时效性"
                "新闻头条的首选工具。当用户询问「今日」「最新」「突发」的宏观政经"
                "或大盘动态时，必须优先调用此工具获取摘要。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "日期，YYYY-MM-DD 格式。留空则返回最新一天的数据",
                    },
                    "tag": {
                        "type": "string",
                        "enum": ["股市财经", "时政要闻"],
                        "description": "资讯类型。留空则返回所有类型",
                    },
                },
                "required": [],
            },
        )

    def execute(self, args: dict) -> dict:
        date_str = args.get("date", "").strip()
        tag = args.get("tag", "").strip()

        # 解析日期
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d")
                file_date = target_date.strftime("%Y%m%d")
            except ValueError:
                return {"text": f"日期格式错误，请使用 YYYY-MM-DD 格式"}
        else:
            # 没给日期 → 找最新的
            file_date = self._find_latest_date()
            if not file_date:
                return {"text": "暂无新闻数据"}

        # 收集匹配的文件
        tag_dirs = [tag] if tag else self._list_tag_dirs()
        all_items = []

        for tag_dir in tag_dirs:
            dirpath = os.path.join(_NEWS_DIR, tag_dir)
            if not os.path.isdir(dirpath):
                continue
            for fname in os.listdir(dirpath):
                if file_date not in fname or not fname.endswith(".json"):
                    continue
                fpath = os.path.join(dirpath, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        items = json.load(f)
                    for item in items:
                        item["_tag"] = tag_dir
                        item["_source"] = fname.replace(f"_{file_date}.json", "")
                    all_items.extend(items)
                except Exception as e:
                    logger.warning("读取 %s 失败: %s", fpath, e)

        if not all_items:
            hint = f"{date_str or '最新'}"
            tag_hint = f"【{tag}】" if tag else ""
            return {"text": f"{tag_hint}{hint}暂无新闻数据"}

        # 格式化输出
        lines = []
        if tag:
            lines.append(f"== {tag} ==")
        lines.append(f"共 {len(all_items)} 条资讯\n")

        # 按源分组
        by_source: dict[str, list[dict]] = {}
        for item in all_items:
            source = item.get("_source", item.get("feed_name", "未知"))
            by_source.setdefault(source, []).append(item)

        for source, items in by_source.items():
            tag_label = items[0].get("_tag", "")
            lines.append(f"【{source}】{tag_label}")
            for item in items:
                title = item.get("title", "")
                desc = item.get("description", "")
                # 取 description 第一段作为摘要
                summary = desc.strip()
                lines.append(f"  {title}")
                if summary:
                    lines.append(f"    {summary[:200]}")
                lines.append("")
            lines.append("")

        return {"text": "\n".join(lines)}

    def _find_latest_date(self) -> str | None:
        """扫描目录，找最新一天的文件日期"""
        latest = ""
        for tag_dir in self._list_tag_dirs():
            dirpath = os.path.join(_NEWS_DIR, tag_dir)
            if not os.path.isdir(dirpath):
                continue
            for fname in os.listdir(dirpath):
                if not fname.endswith(".json"):
                    continue
                # 文件名格式: 名称_YYYYMMDD.json
                parts = fname.split("_")
                if len(parts) >= 2:
                    date_part = parts[-1].replace(".json", "")
                    if date_part.isdigit() and date_part > latest:
                        latest = date_part
        return latest or None

    @staticmethod
    def _list_tag_dirs() -> list[str]:
        if not os.path.isdir(_NEWS_DIR):
            return []
        return sorted([
            d for d in os.listdir(_NEWS_DIR)
            if os.path.isdir(os.path.join(_NEWS_DIR, d))
        ])


registry.register(ReadNewsTool())
