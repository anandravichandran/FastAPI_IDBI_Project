"""Unit tests for the deterministic budget-planning engine."""
from __future__ import annotations

import pytest

from budget.core.config import Settings
from budget.core.exceptions import DomainValidationError
from budget.domain.entities import BudgetRequestData, Expense, IncomeSource
from budget.domain.enums import (
    AlertLevel,
    AlertType,
    BudgetBucket,
    ExpenseCategory,
    Frequency,
    to_monthly,
)
from budget.services.budget_planner import BudgetPlanner


def test_frequency_normalization_to_monthly():
    assert to_monthly(1200, Frequency.ANNUAL) == pytest.approx(100.0)
    assert to_monthly(300, Frequency.QUARTERLY) == pytest.approx(100.0)
    assert to_monthly(100, Frequency.MONTHLY) == 100.0


def test_recommended_budget_uses_50_30_20(planner, healthy_request):
    plan = planner.build_plan(healthy_request)
    rec = plan.recommended_budget
    assert rec.needs == pytest.approx(plan.monthly_income * 0.5)
    assert rec.wants == pytest.approx(plan.monthly_income * 0.3)
    assert rec.savings == pytest.approx(plan.monthly_income * 0.2)


def test_savings_percentage_and_score_for_healthy_budget(planner, healthy_request):
    plan = planner.build_plan(healthy_request)
    assert plan.savings_pct > 20
    assert plan.net_cashflow > 0
    assert plan.budget_score >= 70
    assert plan.grade in {"A", "B"}


def test_breakdown_shares_sum_to_100(planner, healthy_request):
    plan = planner.build_plan(healthy_request)
    assert sum(line.share_pct for line in plan.breakdown) == pytest.approx(100.0, abs=0.5)
    # Every category maps to exactly one bucket.
    for line in plan.breakdown:
        assert line.bucket in BudgetBucket


def test_negative_cashflow_triggers_critical_alerts(planner, overspending_request):
    plan = planner.build_plan(overspending_request)
    assert plan.net_cashflow < 0
    types = {a.type for a in plan.alerts}
    assert AlertType.NEGATIVE_CASHFLOW in types
    assert any(a.level is AlertLevel.CRITICAL for a in plan.alerts)
    assert plan.budget_score < 55
    assert plan.grade in {"D", "E"}


def test_overspending_detection_flags_wants(planner, overspending_request):
    plan = planner.build_plan(overspending_request)
    assert plan.overspending, "expected at least one overspending category"
    for line in plan.overspending:
        assert line.over_budget is True
        assert line.variance > 0


def test_bill_due_soon_alert_only_for_non_autopay(planner, overspending_request):
    plan = planner.build_plan(overspending_request)
    due_soon = [a for a in plan.alerts if a.type is AlertType.BILL_DUE_SOON]
    # Loan EMI (due_day=10, autopay=False) qualifies; Rent (autopay via? no) too.
    assert any("Loan EMI" in a.message for a in due_soon)


def test_zero_income_raises_domain_error(planner):
    bad = BudgetRequestData(
        currency="INR",
        incomes=(IncomeSource("None", 0.0001, Frequency.ANNUAL),),
        expenses=(Expense(ExpenseCategory.FOOD, 100),),
        bills=(),
        goals=(),
    )
    # Income normalizes to a tiny positive number; force true zero instead.
    bad = BudgetRequestData(currency="INR", incomes=(), expenses=(), bills=(), goals=())
    with pytest.raises(DomainValidationError):
        planner.build_plan(bad)


def test_savings_target_is_configurable():
    strict = Settings(savings_target_pct=40)
    planner = BudgetPlanner(strict)
    req = BudgetRequestData(
        currency="INR",
        incomes=(IncomeSource("Salary", 100000, Frequency.MONTHLY),),
        expenses=(Expense(ExpenseCategory.GROCERIES, 20000),),
        bills=(),
        goals=(),
    )
    plan = planner.build_plan(req)
    assert plan.recommended_budget.savings == pytest.approx(40000)
