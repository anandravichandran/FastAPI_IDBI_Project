"""Immutable domain entities and value objects for the Budget Planner.

These are pure Python dataclasses with no framework dependencies — the domain
layer knows nothing about FastAPI or Pydantic. The API layer maps its DTOs to
and from these types, keeping the core independent and testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from budget.domain.enums import (
    AlertLevel,
    AlertType,
    BudgetBucket,
    ExpenseCategory,
    Frequency,
    GoalPriority,
)


@dataclass(frozen=True, slots=True)
class IncomeSource:
    """A single income stream at some cadence."""

    name: str
    amount: float
    frequency: Frequency = Frequency.MONTHLY


@dataclass(frozen=True, slots=True)
class Expense:
    """A (typically variable) spend in a category."""

    category: ExpenseCategory
    amount: float
    frequency: Frequency = Frequency.MONTHLY
    label: str | None = None


@dataclass(frozen=True, slots=True)
class Bill:
    """A recurring fixed obligation, optionally with a due day-of-month."""

    name: str
    amount: float
    category: ExpenseCategory = ExpenseCategory.UTILITIES
    frequency: Frequency = Frequency.MONTHLY
    due_day: int | None = None  # 1..31
    autopay: bool = False


@dataclass(frozen=True, slots=True)
class Goal:
    """A savings goal with an optional monthly contribution and horizon."""

    name: str
    target_amount: float
    saved_amount: float = 0.0
    monthly_contribution: float | None = None
    months_remaining: int | None = None
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
        """Monthly funding needed to stay on track for this goal."""
        if self.monthly_contribution is not None:
            return max(self.monthly_contribution, 0.0)
        if self.months_remaining and self.months_remaining > 0:
            return round(self.remaining / self.months_remaining, 2)
        return 0.0


@dataclass(frozen=True, slots=True)
class BudgetRequestData:
    """Normalized inputs to the planning engine."""

    currency: str
    incomes: tuple[IncomeSource, ...]
    expenses: tuple[Expense, ...]
    bills: tuple[Bill, ...]
    goals: tuple[Goal, ...]


# --- Output value objects ---------------------------------------------------
@dataclass(frozen=True, slots=True)
class CategoryLine:
    category: ExpenseCategory
    bucket: BudgetBucket
    actual: float
    share_pct: float          # share of total spend
    recommended: float        # recommended monthly amount for this category
    variance: float           # actual - recommended (positive = over)
    over_budget: bool


@dataclass(frozen=True, slots=True)
class BucketSummary:
    bucket: BudgetBucket
    actual: float
    actual_pct: float         # of income
    target_pct: float
    recommended: float        # target_pct * income
    variance: float           # actual - recommended
    over_target: bool


@dataclass(frozen=True, slots=True)
class GoalPlan:
    name: str
    target_amount: float
    saved_amount: float
    progress_pct: float
    required_monthly: float
    funded_monthly: float     # how much the plan can actually allocate
    fully_funded: bool
    priority: GoalPriority


@dataclass(frozen=True, slots=True)
class Alert:
    level: AlertLevel
    type: AlertType
    message: str
    category: ExpenseCategory | None = None


@dataclass(frozen=True, slots=True)
class RecommendedBudget:
    needs: float
    wants: float
    savings: float
    currency: str


@dataclass(frozen=True, slots=True)
class BudgetPlan:
    """The complete result of a planning run."""

    currency: str
    monthly_income: float
    total_expenses: float
    total_bills: float
    total_outflow: float
    net_cashflow: float
    savings_amount: float
    savings_pct: float
    recommended_budget: RecommendedBudget
    buckets: tuple[BucketSummary, ...]
    breakdown: tuple[CategoryLine, ...]
    goals: tuple[GoalPlan, ...]
    overspending: tuple[CategoryLine, ...]
    alerts: tuple[Alert, ...]
    budget_score: float
    grade: str
    highlights: tuple[str, ...] = field(default_factory=tuple)
    recommendations: tuple[str, ...] = field(default_factory=tuple)
