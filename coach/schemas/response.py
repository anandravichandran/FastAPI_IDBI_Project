"""Pydantic response models (transport/DTO layer).

The chat response is shaped for a **mobile avatar** client: a short spoken
``reply`` line, an ``avatar`` block driving emotion/animation, structured
``insights`` chips, and tappable ``quick_replies`` / ``action_items``.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from coach.domain.enums import AvatarEmotion, CoachIntent, Verdict


class AvatarState(BaseModel):
    """Drives the on-screen avatar."""

    emotion: AvatarEmotion = AvatarEmotion.NEUTRAL
    animation: str = Field(default="idle", examples=["nod", "thumbs_up", "think"])
    tone: str = Field(default="friendly", examples=["friendly", "cautious"])
    speech: str = Field(..., description="Short text the avatar speaks aloud.")


class Insight(BaseModel):
    """A compact data chip rendered under the avatar."""

    label: str = Field(..., examples=["Savings rate"])
    value: str = Field(..., examples=["24%"])
    status: str = Field(default="neutral", examples=["good", "warn", "bad", "neutral"])


class QuickReply(BaseModel):
    label: str = Field(..., examples=["How can I improve savings?"])
    payload: str = Field(..., description="Message sent back when tapped.")


class SourceRef(BaseModel):
    id: str
    title: str
    source: str
    score: float


class ChatResponse(BaseModel):
    """Mobile-avatar-friendly coaching response."""

    session_id: str
    message_id: str
    customer_id: str
    intent: CoachIntent
    verdict: Verdict
    confidence: float = Field(..., ge=0, le=1)

    reply: str = Field(..., description="Short headline answer for chat bubble.")
    detail: str = Field(..., description="Fuller explanation for the expanded view.")
    avatar: AvatarState
    insights: list[Insight] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    quick_replies: list[QuickReply] = Field(default_factory=list)

    llm_used: bool
    llm_model: str
    sources: list[SourceRef] = Field(default_factory=list)
    disclaimers: list[str] = Field(default_factory=list)
    generated_at: datetime


class HistoryTurn(BaseModel):
    role: str
    content: str
    intent: str | None = None
    created_at: datetime


class HistoryResponse(BaseModel):
    customer_id: str
    session_id: str | None = None
    count: int
    turns: list[HistoryTurn] = Field(default_factory=list)


class CategoryBreakdown(BaseModel):
    category: str
    amount: float
    share_pct: float
    budget_limit: float | None = None
    over_budget: bool = False


class GoalProgress(BaseModel):
    name: str
    target_amount: float
    saved_amount: float
    progress_pct: float
    priority: str


class SummaryResponse(BaseModel):
    """Financial health summary for the coach dashboard / avatar home screen."""

    customer_id: str
    display_name: str
    currency: str
    generated_at: datetime

    monthly_income: float
    monthly_expenses: float
    monthly_surplus: float
    savings_rate_pct: float
    total_savings: float
    emergency_fund_months: float
    total_monthly_emi: float
    foir_pct: float
    financial_health_score: float = Field(..., ge=0, le=100)
    health_grade: str

    top_categories: list[CategoryBreakdown] = Field(default_factory=list)
    overspending: list[CategoryBreakdown] = Field(default_factory=list)
    goals: list[GoalProgress] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    disclaimers: list[str] = Field(default_factory=list)
