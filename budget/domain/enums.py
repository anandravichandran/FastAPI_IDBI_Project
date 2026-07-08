"""Domain enumerations for the Budget Planner."""
from __future__ import annotations

from enum import Enum


class ExpenseCategory(str, Enum):
    """Canonical spend categories used across expenses and bills."""

    HOUSING = "housing"
    FOOD = "food"
    GROCERIES = "groceries"
    TRANSPORT = "transport"
    UTILITIES = "utilities"
    HEALTH = "health"
    INSURANCE = "insurance"
    EDUCATION = "education"
    LOAN_EMI = "loan_emi"
    SHOPPING = "shopping"
    ENTERTAINMENT = "entertainment"
    DINING_OUT = "dining_out"
    SUBSCRIPTIONS = "subscriptions"
    TRAVEL = "travel"
    SAVINGS = "savings"
    INVESTMENTS = "investments"
    OTHER = "other"


class BudgetBucket(str, Enum):
    """The three high-level buckets of the 50/30/20 framework."""

    NEEDS = "needs"
    WANTS = "wants"
    SAVINGS = "savings"


class Frequency(str, Enum):
    """Cadence of a cash flow; everything is normalized to monthly."""

    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class GoalPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    OVERSPENDING = "overspending"
    LOW_SAVINGS = "low_savings"
    NEGATIVE_CASHFLOW = "negative_cashflow"
    HIGH_BILL_BURDEN = "high_bill_burden"
    BILL_DUE_SOON = "bill_due_soon"
    GOAL_UNDERFUNDED = "goal_underfunded"
    BUCKET_OVER_TARGET = "bucket_over_target"
    POSITIVE = "positive"


class BudgetGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


# Mapping of each category to its default 50/30/20 bucket. This is the single
# source of truth for needs/wants/savings classification.
CATEGORY_BUCKET: dict[ExpenseCategory, BudgetBucket] = {
    ExpenseCategory.HOUSING: BudgetBucket.NEEDS,
    ExpenseCategory.FOOD: BudgetBucket.NEEDS,
    ExpenseCategory.GROCERIES: BudgetBucket.NEEDS,
    ExpenseCategory.TRANSPORT: BudgetBucket.NEEDS,
    ExpenseCategory.UTILITIES: BudgetBucket.NEEDS,
    ExpenseCategory.HEALTH: BudgetBucket.NEEDS,
    ExpenseCategory.INSURANCE: BudgetBucket.NEEDS,
    ExpenseCategory.EDUCATION: BudgetBucket.NEEDS,
    ExpenseCategory.LOAN_EMI: BudgetBucket.NEEDS,
    ExpenseCategory.SHOPPING: BudgetBucket.WANTS,
    ExpenseCategory.ENTERTAINMENT: BudgetBucket.WANTS,
    ExpenseCategory.DINING_OUT: BudgetBucket.WANTS,
    ExpenseCategory.SUBSCRIPTIONS: BudgetBucket.WANTS,
    ExpenseCategory.TRAVEL: BudgetBucket.WANTS,
    ExpenseCategory.SAVINGS: BudgetBucket.SAVINGS,
    ExpenseCategory.INVESTMENTS: BudgetBucket.SAVINGS,
    ExpenseCategory.OTHER: BudgetBucket.WANTS,
}


def bucket_for(category: ExpenseCategory) -> BudgetBucket:
    """Return the default budget bucket for a category."""
    return CATEGORY_BUCKET.get(category, BudgetBucket.WANTS)


# Monthly-normalization multipliers for each frequency.
MONTHLY_FACTOR: dict[Frequency, float] = {
    Frequency.WEEKLY: 52 / 12,
    Frequency.BIWEEKLY: 26 / 12,
    Frequency.MONTHLY: 1.0,
    Frequency.QUARTERLY: 1 / 3,
    Frequency.ANNUAL: 1 / 12,
}


def to_monthly(amount: float, frequency: Frequency) -> float:
    """Normalize an amount at a given cadence to a monthly figure."""
    return amount * MONTHLY_FACTOR[frequency]
