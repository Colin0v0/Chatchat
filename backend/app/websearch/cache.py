from __future__ import annotations

from collections import OrderedDict
import time

from .types import WebSearchResult


class WebSearchCache:
    def __init__(self, ttl_seconds: float = 300.0, max_entries: int = 128):
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._store: OrderedDict[str, tuple[float, list[WebSearchResult]]] = OrderedDict()

    def get(self, key: str) -> list[WebSearchResult] | None:
        record = self._store.get(key)
        if record is None:
            return None

        expires_at, results = record
        if expires_at < time.time():
            self._store.pop(key, None)
            return None

        self._store.move_to_end(key)
        return results

    def set(self, key: str, results: list[WebSearchResult]) -> None:
        self._store[key] = (time.time() + self._ttl_seconds, results)
        self._store.move_to_end(key)
        while len(self._store) > self._max_entries:
            self._store.popitem(last=False)
