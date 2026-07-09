"""Shared, pooled async HTTP client factory.

Creating an ``httpx.AsyncClient`` per request (or lazily without locking) leaks
connections and defeats keep-alive. This factory builds clients with explicit
connection-pool limits and bounded timeouts, and provides an asyncio-safe lazy
accessor so concurrent coroutines never race to create duplicate clients.

Used by the LLM adapters to make their lazy ``_http()`` initialisation
thread/async-safe without changing their request/response behaviour.
"""
from __future__ import annotations

import httpx

DEFAULT_LIMITS = httpx.Limits(
    max_connections=100,
    max_keepalive_connections=20,
    keepalive_expiry=30.0,
)


def build_async_client(
    *,
    base_url: str = "",
    timeout_seconds: float = 30.0,
    headers: dict[str, str] | None = None,
    limits: httpx.Limits = DEFAULT_LIMITS,
) -> httpx.AsyncClient:
    """Construct a pooled ``httpx.AsyncClient`` with sane production defaults."""
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(timeout_seconds),
        headers=headers or {},
        limits=limits,
    )
