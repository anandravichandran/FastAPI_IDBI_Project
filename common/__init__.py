"""Shared, cross-cutting production concerns for the Financial Suite.

This package centralises the hardening that every sub-application needs so the
fixes live in exactly one place (DRY) and can be wired into the mounted parent
app with a single call. Nothing here changes business logic or API contracts:
it adds authentication, security headers, trusted-host + CORS policy, edge
rate-limiting, SSRF guards and resilience primitives (circuit breaker, pooled
HTTP client) around the existing routes.
"""
from __future__ import annotations

__all__ = ["__version__"]

__version__ = "1.0.0"
