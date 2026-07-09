"""Edge-case API tests for the Investment Advisor.

Reuses the shared `client` fixture from tests/advisor/conftest.py (which wires
the advisor app with fake LLM + fake market data). Focuses on input-validation
boundaries that a banking reviewer must confirm are enforced.
"""
from __future__ import annotations

import pytest

ADVICE = "/api/v1/advisor/advice"


def _valid_request() -> dict:
    return {
        "user_profile": {
            "full_name": "Test User",
            "age": 30,
            "dependents": 0,
            "country": "IN",
            "currency": "INR",
            "employment_status": "salaried",
        },
        "risk_profile": {
            "tolerance": "moderate",
            "investment_horizon_years": 10,
            "has_stable_income": True,
        },
        "monthly_income": 100000,
        "monthly_expenses": 40000,
        "current_savings": 500000,
        "goals": [],
        "current_portfolio": [],
    }


def test_missing_body_returns_422(client) -> None:
    resp = client.post(ADVICE)
    assert resp.status_code == 422


def test_empty_object_returns_422(client) -> None:
    resp = client.post(ADVICE, json={})
    assert resp.status_code == 422


@pytest.mark.parametrize("age", [-1, 0, 17, 101, 1000])
def test_age_out_of_range_rejected(client, age: int) -> None:
    body = _valid_request()
    body["user_profile"]["age"] = age
    resp = client.post(ADVICE, json=body)
    assert resp.status_code == 422


@pytest.mark.parametrize("field", ["monthly_income", "monthly_expenses"])
def test_negative_amounts_rejected(client, field: str) -> None:
    body = _valid_request()
    body[field] = -100
    resp = client.post(ADVICE, json=body)
    assert resp.status_code == 422


def test_implausible_cashflow_rejected(client) -> None:
    # expenses > 3x income should trip the guardrail validator (-> 422).
    body = _valid_request()
    body["monthly_income"] = 10000
    body["monthly_expenses"] = 90000
    resp = client.post(ADVICE, json=body)
    assert resp.status_code == 422


def test_extra_forbidden_field_rejected(client) -> None:
    body = _valid_request()
    body["is_admin"] = True
    resp = client.post(ADVICE, json=body)
    assert resp.status_code == 422


def test_valid_request_succeeds_with_fake_llm(client) -> None:
    resp = client.post(ADVICE, json=_valid_request())
    assert resp.status_code == 200
