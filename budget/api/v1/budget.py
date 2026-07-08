"""Budget planning endpoint.

Thin controller: it maps the validated request DTO into framework-free domain
entities, delegates all reasoning to :class:`BudgetPlanner`, and maps the
resulting domain plan back to the response DTO. No business logic lives here.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from budget.api.deps import get_planner
from budget.domain.entities import (
    Bill,
    BudgetRequestData,
    Expense,
    Goal,
    IncomeSource,
)
from budget.schemas.request import BudgetRequest
from budget.schemas.response import BudgetResponse
from budget.services.budget_planner import BudgetPlanner

router = APIRouter(prefix="/budget", tags=["budget"])


def _to_domain(payload: BudgetRequest) -> BudgetRequestData:
    return BudgetRequestData(
        currency=payload.currency,
        incomes=tuple(
            IncomeSource(name=i.name, amount=i.amount, frequency=i.frequency)
            for i in payload.incomes
        ),
        expenses=tuple(
            Expense(category=e.category, amount=e.amount, frequency=e.frequency, label=e.label)
            for e in payload.expenses
        ),
        bills=tuple(
            Bill(
                name=b.name, amount=b.amount, category=b.category,
                frequency=b.frequency, due_day=b.due_day, autopay=b.autopay,
            )
            for b in payload.bills
        ),
        goals=tuple(
            Goal(
                name=g.name, target_amount=g.target_amount, saved_amount=g.saved_amount,
                monthly_contribution=g.monthly_contribution,
                months_remaining=g.months_remaining, priority=g.priority,
            )
            for g in payload.goals
        ),
    )


@router.post(
    "/plan",
    response_model=BudgetResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a monthly budget plan",
    description=(
        "Analyze income, expenses, bills and goals to produce a recommended "
        "monthly budget, expense breakdown, savings percentage, alerts, "
        "overspending detection and an overall budget score."
    ),
)
async def plan_budget(
    payload: BudgetRequest,
    planner: BudgetPlanner = Depends(get_planner),
) -> BudgetResponse:
    plan = planner.build_plan(_to_domain(payload))
    return BudgetResponse.from_domain(plan)
