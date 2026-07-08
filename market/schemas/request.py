"""Request DTOs."""
from __future__ import annotations

from pydantic import BaseModel, Field


class NewsRequest(BaseModel):
    """Body for POST /news."""

    query: str | None = Field(default=None, description="Free-text search query.")
    symbols: list[str] | None = Field(
        default=None, description="Ticker symbols to fetch company news for."
    )
    limit: int | None = Field(
        default=None, ge=1, le=100, description="Maximum number of articles."
    )
