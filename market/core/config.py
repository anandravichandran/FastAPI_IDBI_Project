"""Application configuration (12-factor, environment-driven).

All settings are overridable via environment variables (prefix ``MARKET_``) or a
``.env`` file. Uses ``pydantic-settings`` when available and degrades to a small
plain-class shim in minimal/offline environments so the module always imports.

The settings object is hashable so it can key the ``lru_cache`` on the
composition root, giving a single shared service instance per configuration.
"""
from __future__ import annotations

from functools import lru_cache

try:  # pragma: no cover - exercised implicitly by environment
    from pydantic_settings import BaseSettings, SettingsConfigDict

    _HAS_PYDANTIC_SETTINGS = True
except Exception:  # pragma: no cover - offline fallback
    _HAS_PYDANTIC_SETTINGS = False


if _HAS_PYDANTIC_SETTINGS:

    class Settings(BaseSettings):
        """Strongly-typed, environment-driven configuration."""

        model_config = SettingsConfigDict(
            env_prefix="MARKET_",
            env_file=".env",
            extra="ignore",
            frozen=True,
        )

        app_name: str = "OpenBB Market Data Service"
        app_version: str = "1.0.0"
        environment: str = "development"

        provider_backend: str = "openbb"  # "openbb" | "synthetic"
        openbb_pat: str | None = None
        openbb_equity_provider: str | None = None
        default_currency: str = "USD"

        cache_enabled: bool = True
        cache_max_entries: int = 2048
        cache_ttl_quote: float = 30.0
        cache_ttl_historical: float = 900.0
        cache_ttl_ratios: float = 3600.0
        cache_ttl_news: float = 300.0
        cache_ttl_reference: float = 86400.0

        retry_max_attempts: int = 3
        retry_base_delay: float = 0.25
        retry_max_delay: float = 5.0
        retry_jitter: float = 0.1

        rate_limit_enabled: bool = True
        rate_limit_rpm: int = 120
        rate_limit_burst: int = 30
        rate_limit_acquire_timeout: float = 0.0

        default_interval: str = "1d"
        max_history_points: int = 2000
        default_history_days: int = 365
        default_news_limit: int = 20
        max_news_limit: int = 100

        @property
        def is_production(self) -> bool:
            return self.environment.lower() in {"production", "prod"}

        @property
        def allow_backend_fallback(self) -> bool:
            return not self.is_production

        @property
        def rate_limit_per_second(self) -> float:
            return max(0.001, self.rate_limit_rpm / 60.0)

else:  # pragma: no cover - offline shim

    import os

    def _b(name: str, default: bool) -> bool:
        return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}

    def _f(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, default))
        except (TypeError, ValueError):
            return default

    def _i(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, default))
        except (TypeError, ValueError):
            return default

    class Settings:  # type: ignore[no-redef]
        """Minimal env-driven settings used when pydantic-settings is absent."""

        __slots__ = (
            "app_name", "app_version", "environment", "provider_backend",
            "openbb_pat", "openbb_equity_provider", "default_currency",
            "cache_enabled", "cache_max_entries", "cache_ttl_quote",
            "cache_ttl_historical", "cache_ttl_ratios", "cache_ttl_news",
            "cache_ttl_reference", "retry_max_attempts", "retry_base_delay",
            "retry_max_delay", "retry_jitter", "rate_limit_enabled",
            "rate_limit_rpm", "rate_limit_burst", "rate_limit_acquire_timeout",
            "default_interval", "max_history_points", "default_history_days",
            "default_news_limit", "max_news_limit",
        )

        def __init__(self, **overrides: object) -> None:
            p = "MARKET_"
            self.app_name = os.getenv(p + "APP_NAME", "OpenBB Market Data Service")
            self.app_version = os.getenv(p + "APP_VERSION", "1.0.0")
            self.environment = os.getenv(p + "ENVIRONMENT", "development")
            self.provider_backend = os.getenv(p + "PROVIDER_BACKEND", "openbb")
            self.openbb_pat = os.getenv(p + "OPENBB_PAT") or None
            self.openbb_equity_provider = os.getenv(p + "OPENBB_EQUITY_PROVIDER") or None
            self.default_currency = os.getenv(p + "DEFAULT_CURRENCY", "USD")
            self.cache_enabled = _b(p + "CACHE_ENABLED", True)
            self.cache_max_entries = _i(p + "CACHE_MAX_ENTRIES", 2048)
            self.cache_ttl_quote = _f(p + "CACHE_TTL_QUOTE", 30.0)
            self.cache_ttl_historical = _f(p + "CACHE_TTL_HISTORICAL", 900.0)
            self.cache_ttl_ratios = _f(p + "CACHE_TTL_RATIOS", 3600.0)
            self.cache_ttl_news = _f(p + "CACHE_TTL_NEWS", 300.0)
            self.cache_ttl_reference = _f(p + "CACHE_TTL_REFERENCE", 86400.0)
            self.retry_max_attempts = _i(p + "RETRY_MAX_ATTEMPTS", 3)
            self.retry_base_delay = _f(p + "RETRY_BASE_DELAY", 0.25)
            self.retry_max_delay = _f(p + "RETRY_MAX_DELAY", 5.0)
            self.retry_jitter = _f(p + "RETRY_JITTER", 0.1)
            self.rate_limit_enabled = _b(p + "RATE_LIMIT_ENABLED", True)
            self.rate_limit_rpm = _i(p + "RATE_LIMIT_RPM", 120)
            self.rate_limit_burst = _i(p + "RATE_LIMIT_BURST", 30)
            self.rate_limit_acquire_timeout = _f(p + "RATE_LIMIT_ACQUIRE_TIMEOUT", 0.0)
            self.default_interval = os.getenv(p + "DEFAULT_INTERVAL", "1d")
            self.max_history_points = _i(p + "MAX_HISTORY_POINTS", 2000)
            self.default_history_days = _i(p + "DEFAULT_HISTORY_DAYS", 365)
            self.default_news_limit = _i(p + "DEFAULT_NEWS_LIMIT", 20)
            self.max_news_limit = _i(p + "MAX_NEWS_LIMIT", 100)
            for key, value in overrides.items():
                if key in self.__slots__:
                    setattr(self, key, value)

        def __hash__(self) -> int:
            return hash(tuple(getattr(self, s) for s in self.__slots__))

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, Settings):
                return NotImplemented
            return all(getattr(self, s) == getattr(other, s) for s in self.__slots__)

        @property
        def is_production(self) -> bool:
            return self.environment.lower() in {"production", "prod"}

        @property
        def allow_backend_fallback(self) -> bool:
            return not self.is_production

        @property
        def rate_limit_per_second(self) -> float:
            return max(0.001, self.rate_limit_rpm / 60.0)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached Settings instance."""
    return Settings()
