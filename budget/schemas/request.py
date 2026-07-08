"""Inbound request DTOs for the Budget Planner API.

These Pydantic models validate and document the wire format. They are mapped
into framework-free domain entities in :mod:`budget.api.v1.budget`, keeping the
service layer independent of FastAPI/Pydantic.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from budget.domain.enums import (
    ExpenseCategory,
    Frequency,
    GoalPriority,
)


class IncomeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., examples=["Salary"])
    amount: float = Field(..., gt=0, examples=[220000])
    frequency: Frequency = Frequency.MONTHLY


class ExpenseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: ExpenseCategory
    amount: float = Field(..., ge=0, examples=[18000])
    frequency: Frequency = Frequency.MONTHLY
    label: str | None = None


class BillIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., examples=["Rent"])
    amount: float = Field(..., ge=0, examples=[45000])
    category: ExpenseCategory = ExpenseCategory.UTILITIES
    frequency: Frequency = Frequency.MONTHLY
    due_day: int | None = Field(default=None, ge=1, le=31, examples=[5])
    autopay: bool = False


class GoalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., examples=["Emergency Fund"])
    target_amount: float = Field(..., gt=0, examples=[600000])
    saved_amount: float = Field(default=0.0, ge=0, examples=[150000])
    monthly_contribution: float | None = Field(default=None, ge=0)
    months_remaining: int | None = Field(default=None, ge=1)
    priority: GoalPriority = GoalPriority.MEDIUM


class BudgetRequest(BaseModel):
    """Full planning request: income, expenses, bills and goals."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "currency": "INR",
                "incomes": [{"name": "Salary", "amount": 220000, "frequency": "monthly"}],
                "expenses": [
                    {"category": "groceries", "amount": 18000},
                    {"category": "dining_out", "amount": 12000},
                    {"category": "entertainment", "amount": 9000},
                    {"category": "transport", "amount": 8000},
                    {"category": "shopping", "amount": 15000},
                ],
                "bills": [
                    {"name": "Rent", "amount": 45000, "category": "housing", "due_day": 5},
                    {"name": "Electricity", "amount": 3500, "category": "utilities", "due_day": 12},
                    {"name": "Car EMI", "amount": 16000, "category": "loan_emi", "autopay": True},
                    {"name": "Health Insurance", "amount": 4000, "category": "insurance", "autopay": True},
                ],
                "goals": [
                    {"name": "Emergency Fund", "target_amount": 600000,
                     "saved_amount": 150000, "months_remaining": 18, "priority": "high"},
                    {"name": "Vacation", "target_amount": 300000,
                     "saved_amount": 40000, "monthly_contribution": 15000, "priority": "low"},
                ],
            }
        },
    )

    currency: str = Field(default="INR", min_length=1, max_length=8)
    incomes: list[IncomeIn] = Field(..., min_length=1)
    expenses: list[ExpenseIn] = Field(default_factory=list)
    bills: list[BillIn] = Field(default_factory=list)
    goals: list[GoalIn] = Field(default_factory=list)
