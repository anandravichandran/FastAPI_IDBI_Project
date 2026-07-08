"""In-memory TTL + LRU cache implementing :class:`ICache`.

Thread-safe for the common CPython case via a coarse lock. Eviction is O(1)
using an ``OrderedDict`` as an LRU; entries also carry an absolute expiry so
stale values are lazily purged on read. A ``time_func`` is injectable so tests
can advance a virtual clock deterministically.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Callable

from market.domain.interfaces.cache import ICache


class TTLCache(ICache):
    def __init__(
        self,
        *,
        max_entries: int = 2048,
        time_func: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_entries = max(1, int(max_entries))
        self._now = time_func
        self._data: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._misses += 1
                return None
            expiry, value = entry
            if expiry <= self._now():
                del self._data[key]
                self._expirations += 1
                self._misses += 1
                return None
            self._data.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any, *, ttl: float) -> None:
        if ttl is None or ttl <= 0:
            return
        expiry = self._now() + float(ttl)
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = (expiry, value)
            while len(self._data) > self._max_entries:
                self._data.popitem(last=False)
                self._evictions += 1

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total) if total else 0.0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "expirations": self._expirations,
                "size": len(self._data),
                "max_entries": self._max_entries,
                "hit_rate": round(hit_rate, 4),
            }
