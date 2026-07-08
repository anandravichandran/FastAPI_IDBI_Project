"""Shared fixtures for the Savings Optimizer tests. Fully offline — the engine
is pure, so no network, LLM or repositories are involved.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from savings.core.config import Settings
from savings.domain.entities import Goal, Loan, SavingsRequestData
from savings.domain.enums import GoalPriority, RiskProfile
from savings.main import create_app
from savings.services.savings_optimizer import SavingsOptimizer


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def optimizer(settings: Settings) -> SavingsOptimizer:
    return SavingsOptimizer(settings)


@pytest.fixture
def funded_request() -> SavingsRequestData:
    """Comfortable saver whose emergency fund is already fully funded."""
    return SavingsRequestData(
        currency="INR",
        monthly_salary=220000,
        monthly_expenses=90000,
        current_savings=1200000,  # well above 6 * (90000 + 16000)
        risk_profile=RiskProfile.MODERATE,
        loans=(Loan("Car Loan", emi=16000, outstanding=480000, interest_rate_pct=9.5),),
        goals=(
            Goal("Child Education", 2500000, saved_amount=200000,
                 horizon_months=120, priority=GoalPriority.MEDIUM),
        ),
    )


@pytest.fixture
def underfunded_request() -> SavingsRequestData:
    """Thin surplus and no emergency buffer yet."""
    return SavingsRequestData(
        currency="INR",
        monthly_salary=90000,
        monthly_expenses=60000,
        current_savings=20000,
        risk_profile=RiskProfile.MODERATE,
        loans=(Loan("Personal Loan", emi=18000),),
        goals=(
            Goal("Vacation", 200000, saved_amount=10000,
                 horizon_months=12, priority=GoalPriority.LOW),
        ),
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
