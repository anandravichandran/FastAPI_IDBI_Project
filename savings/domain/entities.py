"""Immutable domain entities and value objects for the Savings Optimizer.

Pure Python dataclasses with no framework dependencies — the domain layer knows
nothing about FastAPI or Pydantic. The API layer maps its DTOs to/from these
types, keeping the core independent and unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from savings.domain.enums import (
    AlertLevel,
    EmergencyFundStatus,
    GoalPriority,
    Instrument,
    RiskProfile,
)


# --- Inputs -----------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Loan:
    """An outstanding loan with its monthly EMI."""

    name: str
    emi: float                       # monthly instalment
    outstanding: float = 0.0
    interest_rate_pct: float | None = None
    months_remaining: int | None = None


@dataclass(frozen=True, slots=True)
class Goal:
    """A savings goal with an amount, horizon and priority."""

    name: str
    target_amount: float
    saved_amount: float = 0.0
    horizon_months: int | None = None
    priority: GoalPriority = GoalPriority.MEDIUM

    @property
    def remaining(self) -> float:
        return max(self.target_amount - self.saved_amount, 0.0)

    @property
    def progress_pct(self) -> float:
        if self.target_amount <= 0:
            return 100.0
        return round(min(self.saved_amount / self.target_amount, 1.0) * 100, 2)

    def required_monthly(self) -> float:
        if self.horizon_months and self.horizon_months > 0:
            return round(self.remaining / self.horizon_months, 2)
        return 0.0


@dataclass(frozen=True, slots=True)
class SavingsRequestData:
    """Normalized inputs to the optimizer."""

    currency: str
    monthly_salary: float            # net/take-home monthly income
    monthly_expenses: float          # total monthly living expenses (excl. EMIs)
    current_savings: float           # existing liquid savings / corpus
    loans: tuple[Loan, ...]
    goals: tuple[Goal, ...]
    risk_profile: RiskProfile = RiskProfile.MODERATE


# --- Output value objects ---------------------------------------------------
@dataclass(frozen=True, slots=True)
class EmergencyFund:
    target: float
    current: float
    coverage_ratio: float            # current / target
    months_covered: float            # how many months current savings covers
    shortfall: float
    monthly_top_up: float            # suggested monthly contribution to close gap
    status: EmergencyFundStatus


@dataclass(frozen=True, slots=True)
class AllocationLine:
    instrument: Instrument
    percentage: float                # share of monthly saving
    monthly_amount: float
    rationale: str


@dataclass(frozen=True, slots=True)
class GoalProjection:
    name: str
    target_amount: float
    saved_amount: float
    progress_pct: float
    required_monthly: float
    funded_monthly: float
    on_track: bool
    priority: GoalPriority


@dataclass(frozen=True, slots=True)
class Alert:
    level: AlertLevel
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class SavingsPlan:
    """The complete result of an optimization run."""

    currency: str
    monthly_salary: float
    monthly_expenses: float
    total_emi: float
    disposable_income: float         # salary - expenses - emi
    recommended_monthly_saving: float
    savings_rate_pct: float
    foir_pct: float                  # EMI / salary
    emergency_fund: EmergencyFund
    recommended_sip: float
    recommended_fixed_deposit: float
    recommended_liquid_fund: float
    investment_allocation: tuple[AllocationLine, ...]
    risk_profile: RiskProfile
    goals: tuple[GoalProjection, ...]
    alerts: tuple[Alert, ...]
    savings_score: float
    grade: str
    highlights: tuple[str, ...] = field(default_factory=tuple)
    recommendations: tuple[str, ...] = field(default_factory=tuple)
