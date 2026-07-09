"""TTS 缓存 — MD5(text|backend) → WAV 文件 + JSON 索引"""
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("playback_services")

_INDEX_FILE = "index.json"


class TTSCache:
    """文件级 TTS 缓存，无需外部数据库依赖"""

    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.cache_dir / _INDEX_FILE
        self._index: dict[str, dict] = {}
        self._load_index()

    # ---- 索引读写 ----

    def _load_index(self):
        if self._index_path.is_file():
            try:
                with open(self._index_path, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
            except Exception as e:
                logger.warning("TTS 缓存索引加载失败: %s", e)
                self._index = {}
        logger.info("TTS 缓存加载: %d 条", len(self._index))

    def _save_index(self):
        try:
            with open(self._index_path, "w", encoding="utf-8") as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("TTS 缓存索引保存失败: %s", e)

    # ---- 核心方法 ----

    @staticmethod
    def _hash(text: str, backend: str) -> str:
        return hashlib.md5(f"{text}|{backend}".encode("utf-8")).hexdigest()

    def get(self, text: str, backend: str = "edge") -> Optional[Path]:
        """命中返回缓存路径，否则 None"""
        h = self._hash(text, backend)
        entry = self._index.get(h)
        if entry:
            path = self.cache_dir / entry["filename"]
            if path.is_file():
                # 更新访问计数和时间
                entry["hit_count"] = entry.get("hit_count", 0) + 1
                entry["last_access"] = time.time()
                self._save_index()
                logger.debug("TTS 缓存命中: %s", h)
                return path
            else:
                # 文件丢失，清理索引
                logger.warning("TTS 缓存文件丢失，清理索引: %s", h)
                del self._index[h]
                self._save_index()
        return None

    def save(self, text: str, audio_data: bytes, ext: str = ".wav",
             backend: str = "edge") -> Path:
        """合成后写入缓存，返回缓存路径

        Args:
            text: 合成文本
            audio_data: 音频二进制数据
            ext: 文件扩展名（.wav / .mp3）
            backend: 后端名称
        Returns:
            缓存文件路径
        """
        h = self._hash(text, backend)
        filename = f"{h}{ext}"
        path = self.cache_dir / filename
        path.write_bytes(audio_data)

        self._index[h] = {
            "text": text,
            "backend": backend,
            "filename": filename,
            "size": len(audio_data),
            "created_at": time.time(),
            "last_access": time.time(),
            "hit_count": 0,
        }
        self._save_index()
        logger.info("TTS 缓存保存: %s (%d bytes)", filename, len(audio_data))
        return path

    def remove(self, cache_id: str) -> bool:
        """按 hash 删除一条缓存"""
        entry = self._index.get(cache_id)
        if not entry:
            return False
        path = self.cache_dir / entry["filename"]
        if path.is_file():
            path.unlink()
        del self._index[cache_id]
        self._save_index()
        logger.info("TTS 缓存删除: %s", cache_id)
        return True

    def clear_all(self):
        """清空全部缓存"""
        for entry in self._index.values():
            path = self.cache_dir / entry["filename"]
            if path.is_file():
                path.unlink()
        self._index.clear()
        self._save_index()
        logger.info("TTS 缓存已全部清空")

    def list_all(self) -> list[dict]:
        """列出所有缓存条目（按创建时间降序）"""
        entries = []
        for h, entry in self._index.items():
            path = self.cache_dir / entry["filename"]
            exists = path.is_file()
            entries.append({
                "id": h,
                "text": entry["text"][:100],  # 前端展示截断
                "text_full": entry["text"],
                "backend": entry.get("backend", "edge"),
                "filename": entry["filename"],
                "size": entry.get("size", 0),
                "size_str": self._format_size(entry.get("size", 0)),
                "created_at": entry.get("created_at", 0),
                "created_at_str": self._format_ts(entry.get("created_at", 0)),
                "last_access": entry.get("last_access", 0),
                "last_access_str": self._format_ts(entry.get("last_access", 0)),
                "hit_count": entry.get("hit_count", 0),
                "file_exists": exists,
            })
        entries.sort(key=lambda e: e["created_at"], reverse=True)
        return entries

    def stats(self) -> dict:
        """缓存统计信息"""
        total_size = 0
        valid_count = 0
        for entry in self._index.values():
            path = self.cache_dir / entry["filename"]
            if path.is_file():
                total_size += path.stat().st_size
                valid_count += 1
        return {
            "total_entries": len(self._index),
            "valid_entries": valid_count,
            "total_size": total_size,
            "total_size_str": self._format_size(total_size),
        }

    # ---- 辅助 ----

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / 1024 / 1024:.1f} MB"

    @staticmethod
    def _format_ts(ts: float) -> str:
        if not ts:
            return ""
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
