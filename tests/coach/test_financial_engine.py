"""Unit tests for the deterministic analytics & affordability engines."""
from __future__ import annotations

import pytest

from coach.core.config import Settings
from coach.domain.enums import CoachIntent, Verdict
from coach.repositories import InMemoryCustomerRepository
from coach.services import AffordabilityEngine, FinancialAnalyzer, IntentClassifier


@pytest.fixture
def profile():
    import asyncio
    repo = InMemoryCustomerRepository()
    return asyncio.get_event_loop().run_until_complete(repo.get_profile("cust-001"))


def test_snapshot_is_consistent(profile):
    analyzer = FinancialAnalyzer(Settings())
    snap = analyzer.build_snapshot(profile)
    assert snap.monthly_income > 0
    # Surplus must equal income minus expenses.
    assert snap.monthly_surplus == pytest.approx(
        snap.monthly_income - snap.monthly_expenses, abs=0.01
    )
    # Savings rate is bounded and internally consistent.
    assert -100 <= snap.savings_rate_pct <= 100
    assert snap.emergency_fund_months >= 0
    assert snap.foir_pct >= 0


def test_health_score_bounds(profile):
    analyzer = FinancialAnalyzer(Settings())
    snap = analyzer.build_snapshot(profile)
    score, grade = analyzer.health_score(snap)
    assert 0 <= score <= 100
    assert grade in {"A", "B", "C", "D", "E"}


def test_intent_classification_and_amount():
    clf = IntentClassifier()
    intent, conf = clf.classify("Can I afford a home loan of 80 lakh?")
    assert intent == CoachIntent.HOME_LOAN
    assert 0 < conf <= 1
    assert clf.extract_amount("a car worth 12 lakh") == pytest.approx(1_200_000)
    assert clf.extract_amount("budget of 1.2cr") == pytest.approx(12_000_000)
    assert clf.extract_amount("no numbers here") is None


def test_car_assessment_returns_verdict(profile):
    settings = Settings()
    analyzer = FinancialAnalyzer(settings)
    engine = AffordabilityEngine(settings)
    snap = analyzer.build_snapshot(profile)

    cheap = engine.assess_car(snap, profile, price=400_000)
    pricey = engine.assess_car(snap, profile, price=5_000_000)
    assert cheap.verdict in {Verdict.YES, Verdict.CAUTION, Verdict.NO}
    # A very expensive car must not be strictly easier than a cheap one.
    order = {Verdict.YES: 0, Verdict.INFO: 0, Verdict.CAUTION: 1, Verdict.NO: 2}
    assert order[pricey.verdict] >= order[cheap.verdict]
    assert "estimated_emi" in pricey.metrics


def test_home_loan_emi_is_positive(profile):
    settings = Settings()
    analyzer = FinancialAnalyzer(settings)
    engine = AffordabilityEngine(settings)
    snap = analyzer.build_snapshot(profile)
    result = engine.assess_home_loan(snap, profile, property_price=8_000_000)
    assert result.metrics["estimated_emi"] > 0
    assert result.metrics["projected_foir_pct"] >= snap.foir_pct
