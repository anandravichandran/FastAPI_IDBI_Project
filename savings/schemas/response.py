"""Outbound response DTOs for the Savings Optimizer API.

Each model exposes a ``from_domain`` mapper so controllers never hand raw domain
objects to FastAPI — the serialization boundary stays explicit and stable.
"""
from __future__ import annotations

from pydantic import BaseModel

from savings.domain.entities import (
    AllocationLine,
    EmergencyFund,
    GoalProjection,
    SavingsPlan,
)


class EmergencyFundOut(BaseModel):
    target: float
    current: float
    coverage_ratio: float
    months_covered: float
    shortfall: float
    monthly_top_up: float
    status: str

    @classmethod
    def from_domain(cls, ef: EmergencyFund) -> "EmergencyFundOut":
        return cls(
            target=ef.target,
            current=ef.current,
            coverage_ratio=ef.coverage_ratio,
            months_covered=ef.months_covered,
            shortfall=ef.shortfall,
            monthly_top_up=ef.monthly_top_up,
            status=ef.status.value,
        )


class AllocationOut(BaseModel):
    instrument: str
    percentage: float
    monthly_amount: float
    rationale: str

    @classmethod
    def from_domain(cls, line: AllocationLine) -> "AllocationOut":
        return cls(
            instrument=line.instrument.value,
            percentage=line.percentage,
            monthly_amount=line.monthly_amount,
            rationale=line.rationale,
        )


class GoalOut(BaseModel):
    name: str
    target_amount: float
    saved_amount: float
    progress_pct: float
    required_monthly: float
    funded_monthly: float
    on_track: bool
    priority: str

    @classmethod
    def from_domain(cls, g: GoalProjection) -> "GoalOut":
        return cls(
            name=g.name,
            target_amount=g.target_amount,
            saved_amount=g.saved_amount,
            progress_pct=g.progress_pct,
            required_monthly=g.required_monthly,
            funded_monthly=g.funded_monthly,
            on_track=g.on_track,
            priority=g.priority.value,
        )


class AlertOut(BaseModel):
    level: str
    code: str
    message: str


class SavingsResponse(BaseModel):
    currency: str
    monthly_salary: float
    monthly_expenses: float
    total_emi: float
    disposable_income: float
    recommended_monthly_saving: float
    savings_rate_pct: float
    foir_pct: float
    emergency_fund: EmergencyFundOut
    recommended_sip: float
    recommended_fixed_deposit: float
    recommended_liquid_fund: float
    investment_allocation: list[AllocationOut]
    risk_profile: str
    goals: list[GoalOut]
    alerts: list[AlertOut]
    savings_score: float
    grade: str
    highlights: list[str]
    recommendations: list[str]

    @classmethod
    def from_domain(cls, plan: SavingsPlan) -> "SavingsResponse":
        return cls(
            currency=plan.currency,
            monthly_salary=plan.monthly_salary,
            monthly_expenses=plan.monthly_expenses,
            total_emi=plan.total_emi,
            disposable_income=plan.disposable_income,
            recommended_monthly_saving=plan.recommended_monthly_saving,
            savings_rate_pct=plan.savings_rate_pct,
            foir_pct=plan.foir_pct,
            emergency_fund=EmergencyFundOut.from_domain(plan.emergency_fund),
            recommended_sip=plan.recommended_sip,
            recommended_fixed_deposit=plan.recommended_fixed_deposit,
            recommended_liquid_fund=plan.recommended_liquid_fund,
            investment_allocation=[AllocationOut.from_domain(a) for a in plan.investment_allocation],
            risk_profile=plan.risk_profile.value,
            goals=[GoalOut.from_domain(g) for g in plan.goals],
            alerts=[AlertOut(level=a.level.value, code=a.code, message=a.message) for a in plan.alerts],
            savings_score=plan.savings_score,
            grade=plan.grade,
            highlights=list(plan.highlights),
            recommendations=list(plan.recommendations),
        )
