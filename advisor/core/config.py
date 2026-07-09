"""Environment-based application configuration.

All runtime configuration is loaded from environment variables (or a local
``.env`` file) via ``pydantic-settings``. ``get_settings`` is cached so the
settings object behaves as a process-wide singleton and is trivially
overridable in tests.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "dev", "staging", "production"]


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---------------------------------------------------------
    app_name: str = "Investment Advisor Service"
    app_version: str = "1.0.0"
    environment: Environment = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # --- Logging -------------------------------------------------------------
    log_level: str = "INFO"
    log_json: bool = True

    # --- DeepSeek V3 (OpenAI-compatible chat completions) --------------------
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_seconds: float = 60.0
    deepseek_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    deepseek_max_tokens: int = Field(default=1400, gt=0)

    # --- LLM provider selection ----------------------------------------------
    # "deepseek" (default, talks to api.deepseek.com) or "nvidia" (NVIDIA NIM
    # hosted inference, OpenAI-compatible).
    llm_provider: Literal["deepseek", "nvidia"] = "deepseek"

    # --- NVIDIA NIM (OpenAI-compatible chat completions) ---------------------
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "deepseek-ai/deepseek-v4-pro"
    nvidia_timeout_seconds: float = 60.0
    nvidia_temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    nvidia_top_p: float = Field(default=0.95, ge=0.0, le=1.0)
    nvidia_max_tokens: int = Field(default=16384, gt=0)
    nvidia_thinking: bool = False

    # --- OpenBB market data --------------------------------------------------
    openbb_pat: str | None = None
    openbb_provider: str = "yfinance"
    market_data_timeout_seconds: float = 20.0
    market_benchmark_symbols: list[str] = Field(
        default_factory=lambda: ["SPY", "AGG", "GLD", "VNQ"]
    )

    # --- RAG knowledge retrieval --------------------------------------------
    rag_top_k: int = Field(default=4, gt=0, le=20)
    rag_knowledge_path: str | None = None

    # --- Financial planning defaults ----------------------------------------
    emergency_fund_months: float = Field(default=6.0, gt=0)
    default_expected_inflation_pct: float = 6.0

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def llm_enabled(self) -> bool:
        if self.llm_provider == "nvidia":
            return bool(self.nvidia_api_key)
        return bool(self.deepseek_api_key)


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()
