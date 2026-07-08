"""Inbound request DTOs for the Savings Optimizer API.

Pydantic models validate and document the wire format; they are deliberately
separate from the domain entities so the public contract can evolve
independently of the core.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from savings.domain.enums import GoalPriority, RiskProfile


class LoanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=80)
    emi: float = Field(..., ge=0, description="Monthly instalment amount")
    outstanding: float = Field(default=0.0, ge=0)
    interest_rate_pct: float | None = Field(default=None, ge=0, le=100)
    months_remaining: int | None = Field(default=None, ge=0)


class GoalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=80)
    target_amount: float = Field(..., gt=0)
    saved_amount: float = Field(default=0.0, ge=0)
    horizon_months: int | None = Field(default=None, ge=1, le=600)
    priority: GoalPriority = GoalPriority.MEDIUM


class SavingsRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "currency": "INR",
                "monthly_salary": 220000,
                "monthly_expenses": 95000,
                "current_savings": 300000,
                "risk_profile": "moderate",
                "loans": [
                    {"name": "Car Loan", "emi": 16000, "outstanding": 480000,
                     "interest_rate_pct": 9.5, "months_remaining": 36},
                    {"name": "Home Loan", "emi": 32000, "outstanding": 4200000,
                     "interest_rate_pct": 8.4, "months_remaining": 180},
                ],
                "goals": [
                    {"name": "Emergency Fund", "target_amount": 800000,
                     "saved_amount": 300000, "horizon_months": 12, "priority": "high"},
                    {"name": "Child Education", "target_amount": 2500000,
                     "saved_amount": 200000, "horizon_months": 120, "priority": "medium"},
                    {"name": "Vacation", "target_amount": 300000,
                     "saved_amount": 50000, "horizon_months": 18, "priority": "low"},
                ],
            }
        },
    )

    currency: str = Field(default="INR", min_length=1, max_length=8)
    monthly_salary: float = Field(..., gt=0, description="Net monthly take-home income")
    monthly_expenses: float = Field(..., ge=0, description="Total monthly living expenses excluding EMIs")
    current_savings: float = Field(default=0.0, ge=0, description="Existing liquid savings / corpus")
    risk_profile: RiskProfile = RiskProfile.MODERATE
    loans: list[LoanIn] = Field(default_factory=list)
    goals: list[GoalIn] = Field(default_factory=list)
