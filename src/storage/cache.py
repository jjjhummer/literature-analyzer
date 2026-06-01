"""响应缓存 - 避免重复爬取相同页面"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ResponseCache:
    """基于文件的响应缓存

    用 URL 的 MD5 作为文件名，缓存 HTTP 响应内容。
    自动过期（默认24小时）。
    """

    def __init__(self, cache_dir: Path, ttl_hours: int = 24):
        self.cache_dir = cache_dir
        self.ttl_hours = ttl_hours
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, url: str) -> str:
        """生成缓存键"""
        return hashlib.md5(url.encode("utf-8")).hexdigest()

    def get(self, url: str) -> Optional[str]:
        """获取缓存的响应内容，过期返回 None"""
        key = self._key(url)
        cache_file = self.cache_dir / f"{key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

        # 检查过期
        cached_at = data.get("cached_at", 0)
        age_hours = (time.time() - cached_at) / 3600
        if age_hours > self.ttl_hours:
            cache_file.unlink()
            return None

        logger.debug(f"缓存命中: {url[:80]}... (缓存于 {age_hours:.1f} 小时前)")
        return data.get("content")

    def set(self, url: str, content: str):
        """缓存响应内容"""
        key = self._key(url)
        cache_file = self.cache_dir / f"{key}.json"

        data = {
            "url": url,
            "cached_at": time.time(),
            "content": content,
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def clear(self):
        """清除所有缓存"""
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
        logger.info(f"缓存目录已清空: {self.cache_dir}")

    def clear_expired(self):
        """清除过期缓存"""
        count = 0
        for f in self.cache_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                age_hours = (time.time() - data.get("cached_at", 0)) / 3600
                if age_hours > self.ttl_hours:
                    f.unlink()
                    count += 1
            except Exception:
                f.unlink()
                count += 1

        if count:
            logger.info(f"清除了 {count} 个过期缓存")
