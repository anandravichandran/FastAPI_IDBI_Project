"""Unit tests for the in-memory TTL + LRU cache."""
from __future__ import annotations

from market.repositories.ttl_cache import TTLCache


def test_set_get_roundtrip():
    cache = TTLCache(max_entries=8)
    cache.set("a", 123, ttl=100)
    assert cache.get("a") == 123
    assert cache.stats()["hits"] == 1
    assert cache.stats()["misses"] == 0


def test_miss_counts():
    cache = TTLCache(max_entries=8)
    assert cache.get("missing") is None
    assert cache.stats()["misses"] == 1


def test_expiry_uses_injected_clock():
    now = {"t": 1000.0}
    cache = TTLCache(max_entries=8, time_func=lambda: now["t"])
    cache.set("k", "v", ttl=10)
    assert cache.get("k") == "v"
    now["t"] = 1011.0  # advance beyond ttl
    assert cache.get("k") is None
    assert cache.stats()["expirations"] == 1


def test_ttl_non_positive_skips_storage():
    cache = TTLCache(max_entries=8)
    cache.set("k", "v", ttl=0)
    assert cache.get("k") is None


def test_lru_eviction():
    cache = TTLCache(max_entries=2)
    cache.set("a", 1, ttl=100)
    cache.set("b", 2, ttl=100)
    cache.get("a")  # touch a so b is least-recently-used
    cache.set("c", 3, ttl=100)  # evicts b
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert cache.stats()["evictions"] == 1


def test_invalidate_and_clear():
    cache = TTLCache(max_entries=8)
    cache.set("a", 1, ttl=100)
    cache.invalidate("a")
    assert cache.get("a") is None
    cache.set("b", 2, ttl=100)
    cache.clear()
    assert cache.get("b") is None
