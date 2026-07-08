"""Shared fixtures for the Budget Planner tests. Fully offline — the engine is
pure, so no network, LLM or repositories are involved.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from budget.core.config import Settings
from budget.domain.entities import (
    Bill,
    BudgetRequestData,
    Expense,
    Goal,
    IncomeSource,
)
from budget.domain.enums import ExpenseCategory, Frequency, GoalPriority
from budget.main import create_app
from budget.services.budget_planner import BudgetPlanner


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def planner(settings: Settings) -> BudgetPlanner:
    return BudgetPlanner(settings)


@pytest.fixture
def healthy_request() -> BudgetRequestData:
    """A comfortably-balanced budget (should score well)."""
    return BudgetRequestData(
        currency="INR",
        incomes=(IncomeSource("Salary", 200000, Frequency.MONTHLY),),
        expenses=(
            Expense(ExpenseCategory.GROCERIES, 15000),
            Expense(ExpenseCategory.TRANSPORT, 6000),
            Expense(ExpenseCategory.DINING_OUT, 8000),
            Expense(ExpenseCategory.INVESTMENTS, 30000),
        ),
        bills=(
            Bill("Rent", 40000, ExpenseCategory.HOUSING, due_day=5),
            Bill("Electricity", 3000, ExpenseCategory.UTILITIES, autopay=True),
        ),
        goals=(
            Goal("Emergency Fund", 600000, saved_amount=300000,
                 months_remaining=12, priority=GoalPriority.HIGH),
        ),
    )


@pytest.fixture
def overspending_request() -> BudgetRequestData:
    """Spends more than it earns (should trigger critical alerts)."""
    return BudgetRequestData(
        currency="INR",
        incomes=(IncomeSource("Salary", 100000, Frequency.MONTHLY),),
        expenses=(
            Expense(ExpenseCategory.SHOPPING, 40000),
            Expense(ExpenseCategory.DINING_OUT, 25000),
            Expense(ExpenseCategory.ENTERTAINMENT, 20000),
        ),
        bills=(
            Bill("Rent", 45000, ExpenseCategory.HOUSING, due_day=1),
            Bill("Loan EMI", 20000, ExpenseCategory.LOAN_EMI, autopay=False, due_day=10),
        ),
        goals=(
            Goal("Vacation", 200000, monthly_contribution=10000,
                 priority=GoalPriority.LOW),
        ),
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
