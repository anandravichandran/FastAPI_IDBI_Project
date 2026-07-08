"""Unit tests for the deterministic planning engine."""
from __future__ import annotations

import pytest

from app.domain.enums import EmergencyFundStatus, RiskTolerance
from app.schemas.request import (
    AdviceRequest,
    Goal,
    PortfolioHolding,
    RiskProfile,
    UserProfile,
)


def _request(**overrides) -> AdviceRequest:
    base = dict(
        user_profile=UserProfile(full_name="Test", age=30, dependents=0),
        risk_profile=RiskProfile(tolerance=RiskTolerance.AGGRESSIVE, investment_horizon_years=20),
        monthly_income=200000,
        monthly_expenses=80000,
        current_savings=100000,
        goals=[Goal(name="Wealth", target_amount=10000000)],
        current_portfolio=[
            PortfolioHolding(symbol="SPY", asset_class="equity", current_value=900000),
            PortfolioHolding(symbol="AGG", asset_class="fixed_income", current_value=100000),
        ],
    )
    base.update(overrides)
    return AdviceRequest(**base)


def test_risk_score_bounds(analyzer):
    score = analyzer.compute_risk_score(_request())
    assert 0 <= score.score <= 100
    assert score.band is not None


def test_target_allocation_sums_to_100(analyzer):
    allocation = analyzer.target_allocation(_request())
    total = sum(item.target_pct for item in allocation.target)
    assert total == pytest.approx(100.0, abs=0.1)


def test_emergency_fund_underfunded(analyzer):
    rec = analyzer.emergency_fund(_request(current_savings=0))
    assert rec.status == EmergencyFundStatus.UNDERFUNDED
    assert rec.shortfall > 0


def test_concentration_flagged(analyzer):
    req = _request()
    analysis = analyzer.analyze_portfolio(req)
    assert analysis.largest_position_pct == pytest.approx(90.0, abs=0.1)
    assert any("concentration" in o.lower() for o in analysis.observations)


def test_diversification_score_range(analyzer):
    req = _request()
    analysis = analyzer.analyze_portfolio(req)
    div = analyzer.diversification(req, analysis)
    assert 0 <= div.diversification_score <= 100
    assert div.recommendations
