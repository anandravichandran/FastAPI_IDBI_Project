"""Pydantic request models (transport/DTO layer).

These models validate and document the inbound payload. They are converted
into framework-agnostic domain values inside the service layer.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from advisor.domain.enums import AssetClass, GoalPriority, RiskTolerance


class UserProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(..., min_length=1, max_length=120, examples=["Ada Lovelace"])
    age: int = Field(..., ge=18, le=100, examples=[34])
    dependents: int = Field(default=0, ge=0, le=20)
    country: str = Field(default="IN", min_length=2, max_length=2, examples=["IN"])
    currency: str = Field(default="INR", min_length=3, max_length=3, examples=["INR"])
    employment_status: str = Field(default="salaried", examples=["salaried"])


class RiskProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tolerance: RiskTolerance = Field(..., examples=[RiskTolerance.MODERATE])
    investment_horizon_years: int = Field(..., ge=1, le=60, examples=[15])
    max_drawdown_tolerance_pct: float | None = Field(
        default=None, ge=0, le=100, examples=[25.0]
    )
    has_stable_income: bool = True


class Goal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=120, examples=["Retirement"])
    target_amount: float = Field(..., gt=0, examples=[20_000_000])
    target_date: date | None = Field(default=None)
    priority: GoalPriority = Field(default=GoalPriority.MEDIUM)


class PortfolioHolding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(..., min_length=1, max_length=32, examples=["SPY"])
    asset_class: AssetClass = Field(..., examples=[AssetClass.EQUITY])
    current_value: float = Field(..., ge=0, examples=[500_000])
    units: float | None = Field(default=None, ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)


class AdviceRequest(BaseModel):
    """Full input payload for an investment-advice request."""

    model_config = ConfigDict(extra="forbid")

    user_profile: UserProfile
    risk_profile: RiskProfile
    monthly_income: float = Field(..., ge=0, examples=[250_000])
    monthly_expenses: float = Field(..., ge=0, examples=[120_000])
    current_savings: float = Field(..., ge=0, examples=[1_500_000])
    goals: list[Goal] = Field(default_factory=list, max_length=25)
    current_portfolio: list[PortfolioHolding] = Field(
        default_factory=list, max_length=200
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def monthly_surplus(self) -> float:
        return round(self.monthly_income - self.monthly_expenses, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def portfolio_value(self) -> float:
        return round(sum(h.current_value for h in self.current_portfolio), 2)

    @model_validator(mode="after")
    def _validate_cashflow(self) -> "AdviceRequest":
        if self.monthly_expenses > self.monthly_income * 3:
            # Guardrail against obviously inconsistent inputs.
            raise ValueError(
                "monthly_expenses is implausibly high relative to monthly_income"
            )
        return self
