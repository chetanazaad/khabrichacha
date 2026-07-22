"""
deployment/workspace/cache_manager.py

Shared, disk-backed cache for fetched page content, keyed by URL. Lives at
<workspace_root>/cache/<sha256(url)>.json — this exact file shape
({"url", "title", "content", "cached_at"}) is what
deployment/runtime/retrieval/workspace_index.py's WorkspaceIndex.search_cache()
already expects and scans, so tools should write through this class rather
than writing cache files directly.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional


class CacheManager:
    def __init__(self, workspace_manager):
        self.workspace_manager = workspace_manager
        self.cache_dir: Path = workspace_manager.cache
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _key(url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _path(self, url: str) -> Path:
        return self.cache_dir / f"{self._key(url)}.json"

    def get(self, url: str, max_age_seconds: Optional[int] = None) -> Optional[Dict[str, Any]]:
        path = self._path(url)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if max_age_seconds is not None:
            age = time.time() - data.get("cached_at", 0)
            if age > max_age_seconds:
                return None
        return data

    def set(self, url: str, title: str = "", content: str = "", **extra: Any) -> None:
        payload = {
            "url": url,
            "title": title,
            "content": content,
            "cached_at": time.time(),
            **extra,
        }
        try:
            self._path(url).write_text(json.dumps(payload, default=str), encoding="utf-8")
        except Exception:
            pass

    def clear(self) -> int:
        count = 0
        for f in self.cache_dir.glob("*.json"):
            try:
                f.unlink()
                count += 1
            except Exception:
                pass
        return count
