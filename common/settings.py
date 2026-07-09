"""Process-wide security & hardening settings.

Deliberately dependency-free (reads ``os.environ`` directly) so this shared
module always imports — even in minimal/offline environments — and never
couples the cross-cutting security layer to a specific pydantic-settings
version. Values are resolved once and cached.

All settings are 12-factor / environment-driven. Secrets (API keys, JWT
signing secret) are read from the environment only — never hard-coded.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


def _csv(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class SecuritySettings:
    """Immutable snapshot of the security/hardening configuration."""

    environment: str = "local"
    # Authentication -----------------------------------------------------
    auth_enabled: bool = False
    api_keys: tuple[str, ...] = field(default_factory=tuple)
    api_key_header: str = "X-API-Key"
    jwt_secret: str | None = None
    jwt_algorithms: tuple[str, ...] = ("HS256",)
    jwt_audience: str | None = None
    jwt_issuer: str | None = None
    # CORS ---------------------------------------------------------------
    cors_allow_origins: tuple[str, ...] = ("*",)
    cors_allow_credentials: bool = False
    # Trusted hosts ------------------------------------------------------
    trusted_hosts: tuple[str, ...] = ("*",)
    # Rate limiting ------------------------------------------------------
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 120
    rate_limit_burst: int = 40
    # Security headers ---------------------------------------------------
    security_headers_enabled: bool = True
    hsts_enabled: bool = True
    hsts_max_age: int = 63072000
    # SSRF ---------------------------------------------------------------
    outbound_allowed_hosts: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @classmethod
    def from_env(cls) -> "SecuritySettings":
        environment = os.getenv("ENVIRONMENT", "local")
        is_prod = environment.lower() in {"production", "prod"}
        # Auth is ON by default in production and OFF elsewhere, unless an
        # explicit AUTH_ENABLED override is provided. This keeps local dev and
        # the existing unit-test suite runnable while guaranteeing a secure
        # default for a real banking deployment.
        auth_enabled = _bool("AUTH_ENABLED", default=is_prod)

        cors_origins = _csv("CORS_ALLOW_ORIGINS")
        return cls(
            environment=environment,
            auth_enabled=auth_enabled,
            api_keys=tuple(_csv("API_KEYS")),
            api_key_header=os.getenv("API_KEY_HEADER", "X-API-Key"),
            jwt_secret=os.getenv("JWT_SECRET") or None,
            jwt_algorithms=tuple(_csv("JWT_ALGORITHMS", "HS256")) or ("HS256",),
            jwt_audience=os.getenv("JWT_AUDIENCE") or None,
            jwt_issuer=os.getenv("JWT_ISSUER") or None,
            cors_allow_origins=tuple(cors_origins) if cors_origins else ("*",),
            cors_allow_credentials=_bool("CORS_ALLOW_CREDENTIALS", default=False),
            trusted_hosts=tuple(_csv("TRUSTED_HOSTS")) or ("*",),
            rate_limit_enabled=_bool("RATE_LIMIT_ENABLED", default=is_prod),
            rate_limit_per_minute=_int("RATE_LIMIT_PER_MINUTE", 120),
            rate_limit_burst=_int("RATE_LIMIT_BURST", 40),
            security_headers_enabled=_bool("SECURITY_HEADERS_ENABLED", default=True),
            hsts_enabled=_bool("HSTS_ENABLED", default=True),
            hsts_max_age=_int("HSTS_MAX_AGE", 63072000),
            outbound_allowed_hosts=tuple(_csv("OUTBOUND_ALLOWED_HOSTS")),
        )


@lru_cache
def get_security_settings() -> SecuritySettings:
    return SecuritySettings.from_env()


class EnvironmentValidationError(RuntimeError):
    """Raised at startup when production is misconfigured (fail-closed)."""


def validate_production_env(settings: SecuritySettings | None = None) -> None:
    """Fail fast if a production deployment is missing critical security config.

    A banking service must never boot in production without a working auth
    mechanism or with an unsafe CORS policy. This is invoked at import time in
    ``server.py`` so a misconfigured deploy crashes immediately (and is caught
    by Render's health check) rather than silently serving unauthenticated
    traffic.
    """
    settings = settings or get_security_settings()
    if not settings.is_production:
        return

    errors: list[str] = []
    if settings.auth_enabled:
        if not settings.api_keys and not settings.jwt_secret:
            errors.append(
                "Auth is enabled but neither API_KEYS nor JWT_SECRET is set."
            )
    else:
        errors.append("AUTH_ENABLED must be true in production.")

    if settings.cors_allow_credentials and "*" in settings.cors_allow_origins:
        errors.append(
            "CORS_ALLOW_ORIGINS must not be '*' when credentials are allowed."
        )
    if "*" in settings.trusted_hosts:
        errors.append("TRUSTED_HOSTS must be an explicit allowlist in production.")

    if errors:
        raise EnvironmentValidationError(
            "Invalid production configuration:\n- " + "\n- ".join(errors)
        )
