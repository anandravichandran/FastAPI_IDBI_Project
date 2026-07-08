"""Outbound response DTOs and domain->DTO mapping for the Budget Planner."""
from __future__ import annotations

from pydantic import BaseModel, Field

from budget.domain.entities import BudgetPlan
from budget.domain.enums import (
    AlertLevel,
    AlertType,
    BudgetBucket,
    ExpenseCategory,
    GoalPriority,
)


class RecommendedBudgetOut(BaseModel):
    needs: float
    wants: float
    savings: float
    currency: str


class BucketOut(BaseModel):
    bucket: BudgetBucket
    actual: float
    actual_pct: float
    target_pct: float
    recommended: float
    variance: float
    over_target: bool


class CategoryOut(BaseModel):
    category: ExpenseCategory
    bucket: BudgetBucket
    actual: float
    share_pct: float
    recommended: float
    variance: float
    over_budget: bool


class GoalOut(BaseModel):
    name: str
    target_amount: float
    saved_amount: float
    progress_pct: float
    required_monthly: float
    funded_monthly: float
    fully_funded: bool
    priority: GoalPriority


class AlertOut(BaseModel):
    level: AlertLevel
    type: AlertType
    message: str
    category: ExpenseCategory | None = None


class BudgetResponse(BaseModel):
    """The complete budget plan returned to clients."""

    currency: str
    monthly_income: float = Field(..., description="Income normalized to monthly.")
    total_expenses: float
    total_bills: float
    total_outflow: float = Field(..., description="All non-savings outflow, monthly.")
    net_cashflow: float = Field(..., description="Income minus non-savings outflow.")
    savings_amount: float
    savings_pct: float = Field(..., description="Savings as a percentage of income.")
    recommended_budget: RecommendedBudgetOut
    buckets: list[BucketOut]
    expense_breakdown: list[CategoryOut]
    goals: list[GoalOut]
    overspending: list[CategoryOut]
    alerts: list[AlertOut]
    budget_score: float = Field(..., ge=0, le=100)
    grade: str
    highlights: list[str]
    recommendations: list[str]

    @classmethod
    def from_domain(cls, plan: BudgetPlan) -> "BudgetResponse":
        return cls(
            currency=plan.currency,
            monthly_income=plan.monthly_income,
            total_expenses=plan.total_expenses,
            total_bills=plan.total_bills,
            total_outflow=plan.total_outflow,
            net_cashflow=plan.net_cashflow,
            savings_amount=plan.savings_amount,
            savings_pct=plan.savings_pct,
            recommended_budget=RecommendedBudgetOut(
                needs=plan.recommended_budget.needs,
                wants=plan.recommended_budget.wants,
                savings=plan.recommended_budget.savings,
                currency=plan.recommended_budget.currency,
            ),
            buckets=[
                BucketOut(
                    bucket=b.bucket, actual=b.actual, actual_pct=b.actual_pct,
                    target_pct=b.target_pct, recommended=b.recommended,
                    variance=b.variance, over_target=b.over_target,
                )
                for b in plan.buckets
            ],
            expense_breakdown=[cls._cat(line) for line in plan.breakdown],
            goals=[
                GoalOut(
                    name=g.name, target_amount=g.target_amount,
                    saved_amount=g.saved_amount, progress_pct=g.progress_pct,
                    required_monthly=g.required_monthly, funded_monthly=g.funded_monthly,
                    fully_funded=g.fully_funded, priority=g.priority,
                )
                for g in plan.goals
            ],
            overspending=[cls._cat(line) for line in plan.overspending],
            alerts=[
                AlertOut(level=a.level, type=a.type, message=a.message, category=a.category)
                for a in plan.alerts
            ],
            budget_score=plan.budget_score,
            grade=plan.grade,
            highlights=list(plan.highlights),
            recommendations=list(plan.recommendations),
        )

    @staticmethod
    def _cat(line) -> CategoryOut:  # noqa: ANN001 - internal mapper
        return CategoryOut(
            category=line.category, bucket=line.bucket, actual=line.actual,
            share_pct=line.share_pct, recommended=line.recommended,
            variance=line.variance, over_budget=line.over_budget,
        )
