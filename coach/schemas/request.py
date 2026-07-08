"""Pydantic request models (transport/DTO layer)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """Inbound message to the financial coach."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(..., min_length=1, max_length=64, examples=["cust-001"])
    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        examples=["Can I afford a car worth 12 lakh?"],
    )
    session_id: str | None = Field(
        default=None,
        max_length=64,
        description="Conversation session id. Omit to start a new session.",
        examples=["sess-abc123"],
    )
    locale: str = Field(default="en-IN", max_length=10, examples=["en-IN"])
