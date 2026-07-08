"""Unit tests for the deterministic savings-optimization engine."""
from __future__ import annotations

import pytest

from savings.core.config import Settings
from savings.core.exceptions import DomainValidationError
from savings.domain.entities import Goal, Loan, SavingsRequestData
from savings.domain.enums import (
    EmergencyFundStatus,
    Instrument,
    RiskProfile,
)
from savings.services.savings_optimizer import SavingsOptimizer


def test_disposable_and_monthly_saving(optimizer, funded_request):
    plan = optimizer.build_plan(funded_request)
    # 220000 - 90000 - 16000 = 114000
    assert plan.total_emi == 16000
    assert plan.disposable_income == 114000
    assert plan.recommended_monthly_saving == 114000
    assert plan.savings_rate_pct == pytest.approx(51.82, abs=0.1)


def test_emergency_fund_target_uses_configured_months(optimizer, funded_request):
    plan = optimizer.build_plan(funded_request)
    ef = plan.emergency_fund
    # 6 * (90000 + 16000) = 636000
    assert ef.target == 636000
    assert ef.status is EmergencyFundStatus.FULLY_FUNDED
    assert ef.monthly_top_up == 0.0
    assert ef.coverage_ratio == 1.0


def test_allocation_sums_to_monthly_saving_and_100pct(optimizer, funded_request):
    plan = optimizer.build_plan(funded_request)
    pct = sum(a.percentage for a in plan.investment_allocation)
    amt = sum(a.monthly_amount for a in plan.investment_allocation)
    assert pct == pytest.approx(100.0, abs=0.1)
    assert amt == pytest.approx(plan.recommended_monthly_saving, abs=1.0)
    # Fully-funded moderate saver → SIP is the largest bucket.
    assert plan.recommended_sip >= plan.recommended_fixed_deposit
    assert plan.recommended_sip >= plan.recommended_liquid_fund


def test_sip_fd_liquid_fields_are_populated(optimizer, funded_request):
    plan = optimizer.build_plan(funded_request)
    instruments = {a.instrument for a in plan.investment_allocation}
    assert instruments == {Instrument.SIP, Instrument.FIXED_DEPOSIT, Instrument.LIQUID_FUND}
    assert plan.recommended_sip > 0
    assert plan.recommended_fixed_deposit > 0
    assert plan.recommended_liquid_fund > 0


def test_underfunded_ef_biases_to_liquid(optimizer, underfunded_request):
    plan = optimizer.build_plan(underfunded_request)
    assert plan.emergency_fund.status is EmergencyFundStatus.UNDERFUNDED
    assert plan.emergency_fund.monthly_top_up > 0
    # Building phase → liquid fund gets the biggest share.
    assert plan.recommended_liquid_fund >= plan.recommended_sip
    assert plan.recommended_liquid_fund >= plan.recommended_fixed_deposit


def test_high_debt_triggers_foir_alert():
    optimizer = SavingsOptimizer(Settings())
    req = SavingsRequestData(
        currency="INR", monthly_salary=100000, monthly_expenses=30000,
        current_savings=0, risk_profile=RiskProfile.MODERATE,
        loans=(Loan("Big EMI", emi=50000),), goals=(),
    )
    plan = optimizer.build_plan(req)
    assert plan.foir_pct == 50.0
    codes = {a.code for a in plan.alerts}
    assert "high_debt_burden" in codes


def test_no_surplus_is_critical_and_low_score():
    optimizer = SavingsOptimizer(Settings())
    req = SavingsRequestData(
        currency="INR", monthly_salary=50000, monthly_expenses=45000,
        current_savings=0, risk_profile=RiskProfile.MODERATE,
        loans=(Loan("EMI", emi=10000),), goals=(),
    )
    plan = optimizer.build_plan(req)
    assert plan.disposable_income < 0
    assert plan.recommended_monthly_saving == 0
    codes = {a.code for a in plan.alerts}
    assert "no_surplus" in codes
    assert plan.grade in {"D", "E"}


def test_score_and_grade_bounds(optimizer, funded_request, underfunded_request):
    good = optimizer.build_plan(funded_request)
    weak = optimizer.build_plan(underfunded_request)
    assert 0 <= good.savings_score <= 100
    assert 0 <= weak.savings_score <= 100
    assert good.savings_score > weak.savings_score
    assert good.grade in {"A", "B"}


def test_zero_salary_raises_domain_error(optimizer):
    with pytest.raises(DomainValidationError):
        optimizer.build_plan(SavingsRequestData(
            currency="INR", monthly_salary=0, monthly_expenses=1000,
            current_savings=0, loans=(), goals=(),
        ))


def test_conservative_profile_prefers_fd_over_sip():
    optimizer = SavingsOptimizer(Settings())
    req = SavingsRequestData(
        currency="INR", monthly_salary=200000, monthly_expenses=80000,
        current_savings=1500000, risk_profile=RiskProfile.CONSERVATIVE,
        loans=(), goals=(),
    )
    plan = optimizer.build_plan(req)
    assert plan.emergency_fund.status is EmergencyFundStatus.FULLY_FUNDED
    assert plan.recommended_fixed_deposit > plan.recommended_sip
