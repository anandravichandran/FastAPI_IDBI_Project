"""Tests for the shared production hardening layer (common.*).

These are hermetic: each test builds a throwaway FastAPI app and applies the
middleware with an explicit :class:`SecuritySettings`, so they never depend on
process environment variables or the mounted gateway. They cover the security
controls added during the production-readiness fix pass.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from common.resilience.circuit_breaker import (
    AsyncCircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)
from common.security.auth import AuthMiddleware
from common.security.headers import SecurityHeadersMiddleware
from common.security.ssrf import OutboundURLNotAllowed, validate_base_url
from common.ratelimit import RateLimitMiddleware
from common.settings import SecuritySettings, validate_production_env
from common.settings import EnvironmentValidationError


def _app_with(middleware_cls, settings: SecuritySettings) -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/advisor/api/v1/advisor")
    async def protected() -> dict[str, str]:
        return {"ok": "yes"}

    app.add_middleware(middleware_cls, settings=settings)
    return app


# --- Authentication --------------------------------------------------------
def test_auth_disabled_allows_all():
    settings = SecuritySettings(auth_enabled=False)
    client = TestClient(_app_with(AuthMiddleware, settings))
    assert client.get("/advisor/api/v1/advisor").status_code == 200


def test_auth_enabled_blocks_without_key():
    settings = SecuritySettings(auth_enabled=True, api_keys=("secret-key",))
    client = TestClient(_app_with(AuthMiddleware, settings))
    resp = client.get("/advisor/api/v1/advisor")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_auth_enabled_allows_valid_api_key():
    settings = SecuritySettings(auth_enabled=True, api_keys=("secret-key",))
    client = TestClient(_app_with(AuthMiddleware, settings))
    resp = client.get(
        "/advisor/api/v1/advisor", headers={"X-API-Key": "secret-key"}
    )
    assert resp.status_code == 200


def test_auth_rejects_wrong_api_key():
    settings = SecuritySettings(auth_enabled=True, api_keys=("secret-key",))
    client = TestClient(_app_with(AuthMiddleware, settings))
    resp = client.get("/advisor/api/v1/advisor", headers={"X-API-Key": "nope"})
    assert resp.status_code == 401


def test_auth_exempts_health():
    settings = SecuritySettings(auth_enabled=True, api_keys=("secret-key",))
    client = TestClient(_app_with(AuthMiddleware, settings))
    assert client.get("/health").status_code == 200


# --- Security headers ------------------------------------------------------
def test_security_headers_present():
    settings = SecuritySettings(security_headers_enabled=True)
    client = TestClient(_app_with(SecurityHeadersMiddleware, settings))
    resp = client.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert "Content-Security-Policy" in resp.headers


# --- Rate limiting ---------------------------------------------------------
def test_rate_limit_trips_after_burst():
    settings = SecuritySettings(
        rate_limit_enabled=True, rate_limit_per_minute=60, rate_limit_burst=3
    )
    client = TestClient(_app_with(RateLimitMiddleware, settings))
    statuses = [client.get("/advisor/api/v1/advisor").status_code for _ in range(6)]
    assert 429 in statuses
    # Health is exempt from rate limiting.
    assert client.get("/health").status_code == 200


# --- SSRF ------------------------------------------------------------------
def test_ssrf_allows_public_https_in_allowlist():
    url = "https://api.deepseek.com/v1"
    assert validate_base_url(url, allowed_hosts=["api.deepseek.com"]) == url


def test_ssrf_blocks_loopback():
    with pytest.raises(OutboundURLNotAllowed):
        validate_base_url("http://127.0.0.1:8080", require_https=False)


def test_ssrf_blocks_non_allowlisted_host():
    with pytest.raises(OutboundURLNotAllowed):
        validate_base_url(
            "https://evil.example.com", allowed_hosts=["api.deepseek.com"]
        )


def test_ssrf_blocks_non_https_when_required():
    with pytest.raises(OutboundURLNotAllowed):
        validate_base_url("http://api.deepseek.com")


# --- Circuit breaker -------------------------------------------------------
def test_circuit_breaker_opens_and_fails_fast():
    async def scenario():
        cb = AsyncCircuitBreaker(
            name="t", failure_threshold=2, reset_timeout_seconds=60
        )

        async def boom():
            raise RuntimeError("down")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(boom)
        assert cb.state is CircuitState.OPEN
        with pytest.raises(CircuitBreakerOpen):
            await cb.call(boom)

    asyncio.run(scenario())


def test_circuit_breaker_recovers_after_timeout():
    async def scenario():
        cb = AsyncCircuitBreaker(
            name="t", failure_threshold=1, reset_timeout_seconds=0.0
        )

        async def boom():
            raise RuntimeError("down")

        async def ok():
            return 42

        with pytest.raises(RuntimeError):
            await cb.call(boom)
        assert cb.state is CircuitState.OPEN
        # reset_timeout is 0 => next call transitions to HALF_OPEN then CLOSED.
        assert await cb.call(ok) == 42
        assert cb.state is CircuitState.CLOSED

    asyncio.run(scenario())


# --- Environment validation ------------------------------------------------
def test_validate_production_env_requires_auth_secret():
    settings = SecuritySettings(
        environment="production", auth_enabled=True, api_keys=(), jwt_secret=None
    )
    with pytest.raises(EnvironmentValidationError):
        validate_production_env(settings)


def test_validate_production_env_passes_when_configured():
    settings = SecuritySettings(
        environment="production",
        auth_enabled=True,
        api_keys=("k1",),
        trusted_hosts=("api.bank.example",),
        cors_allow_origins=("https://app.bank.example",),
        cors_allow_credentials=True,
    )
    validate_production_env(settings)  # should not raise


def test_validate_production_env_noop_in_local():
    validate_production_env(SecuritySettings(environment="local"))
