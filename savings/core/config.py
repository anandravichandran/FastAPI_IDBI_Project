"""Application configuration for the Savings Optimizer service.

Every planning rule (emergency-fund horizon, target savings rate, debt ceiling
and the SIP/FD/Liquid allocation presets) is environment-driven via
``pydantic-settings`` so the same image can be tuned per market or product
without code changes. Nothing here is a hard-coded magic number in the engine.
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
    )

    # --- Application ---
    app_name: str = "Savings Optimizer Service"
    app_version: str = "1.0.0"
    environment: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # --- Logging ---
    log_level: str = "INFO"
    log_json: bool = True

    # --- Planning rules ---
    default_currency: str = "INR"
    emergency_fund_months: float = Field(default=6.0, ge=1, le=24)
    healthy_savings_rate_pct: float = Field(default=20.0, ge=0, le=100)
    # FOIR = fixed obligations (EMIs) to income ratio; above this = over-leveraged.
    max_foir_pct: float = Field(default=40.0, ge=0, le=100)
    # Long-horizon threshold (months) that pushes allocation toward equity/SIP.
    long_horizon_months: int = Field(default=60, ge=12)
    short_horizon_months: int = Field(default=36, ge=6)

    # --- Allocation presets (percentages of investable monthly surplus) ---
    # While the emergency fund is still being built, bias strongly to liquid.
    ef_building_sip_pct: float = 20.0
    ef_building_fd_pct: float = 20.0
    ef_building_liquid_pct: float = 60.0

    # Once the emergency fund is fully funded, use risk-based growth presets.
    conservative_sip_pct: float = 30.0
    conservative_fd_pct: float = 45.0
    conservative_liquid_pct: float = 25.0

    moderate_sip_pct: float = 55.0
    moderate_fd_pct: float = 30.0
    moderate_liquid_pct: float = 15.0

    aggressive_sip_pct: float = 70.0
    aggressive_fd_pct: float = 20.0
    aggressive_liquid_pct: float = 10.0


    # --- CORS (SECURITY FIX) --------------------------------------------------
    # Explicit origin allowlist. Never combine "*" with credentials. In
    # production set CORS_ALLOW_ORIGINS to a comma/JSON list of trusted
    # front-end origins and CORS_ALLOW_CREDENTIALS=true only then.
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"])
    cors_allow_credentials: bool = False

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
