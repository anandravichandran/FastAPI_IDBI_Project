"""Savings-optimization endpoint.

Thin controller: it maps the validated request DTO into framework-free domain
entities, delegates all reasoning to :class:`SavingsOptimizer`, and maps the
resulting domain plan back to the response DTO. No business logic lives here.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from savings.api.deps import get_optimizer
from savings.domain.entities import Goal, Loan, SavingsRequestData
from savings.schemas.request import SavingsRequest
from savings.schemas.response import SavingsResponse
from savings.services.savings_optimizer import SavingsOptimizer

router = APIRouter(prefix="/savings", tags=["savings"])


def _to_domain(payload: SavingsRequest) -> SavingsRequestData:
    return SavingsRequestData(
        currency=payload.currency,
        monthly_salary=payload.monthly_salary,
        monthly_expenses=payload.monthly_expenses,
        current_savings=payload.current_savings,
        risk_profile=payload.risk_profile,
        loans=tuple(
            Loan(
                name=l.name, emi=l.emi, outstanding=l.outstanding,
                interest_rate_pct=l.interest_rate_pct,
                months_remaining=l.months_remaining,
            )
            for l in payload.loans
        ),
        goals=tuple(
            Goal(
                name=g.name, target_amount=g.target_amount, saved_amount=g.saved_amount,
                horizon_months=g.horizon_months, priority=g.priority,
            )
            for g in payload.goals
        ),
    )


@router.post(
    "/optimize",
    response_model=SavingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Optimize savings & investment allocation",
    description=(
        "Analyze salary, monthly expenses, loans, savings and goals to produce a "
        "recommended emergency fund, monthly saving, SIP / fixed-deposit / liquid-"
        "fund split, full investment allocation and an overall savings score."
    ),
)
async def optimize_savings(
    payload: SavingsRequest,
    optimizer: SavingsOptimizer = Depends(get_optimizer),
) -> SavingsResponse:
    plan = optimizer.build_plan(_to_domain(payload))
    return SavingsResponse.from_domain(plan)
