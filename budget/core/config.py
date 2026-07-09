"""Application configuration for the Budget Planner service.

All settings are environment-driven via ``pydantic-settings`` so the same
image runs across local/dev/staging/production without code changes. Budgeting
rules (target allocation, thresholds) are configuration, not magic numbers, so
they can be tuned per market or product without a redeploy of logic.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
        frozen=True,
    )

    # --- Application ---
    app_name: str = "Budget Planner Service"
    app_version: str = "1.0.0"
    environment: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # --- Logging ---
    log_level: str = "INFO"
    log_json: bool = True

    # --- Budgeting rules (50/30/20 baseline, all tunable) ---
    needs_target_pct: float = Field(default=50.0, ge=0, le=100)
    wants_target_pct: float = Field(default=30.0, ge=0, le=100)
    savings_target_pct: float = Field(default=20.0, ge=0, le=100)
    # Minimum acceptable savings rate before a critical alert fires.
    min_savings_pct: float = Field(default=10.0, ge=0, le=100)
    # Fixed-bill burden (bills / income) that triggers a warning.
    bill_burden_warn_pct: float = Field(default=35.0, ge=0, le=100)
    # Allowed overshoot above a category's recommended amount before it counts
    # as overspending (percentage points of tolerance).
    overspend_tolerance_pct: float = Field(default=5.0, ge=0, le=100)
    # Default currency assumed when a request omits one.
    default_currency: str = "INR"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
