"""API-level tests for the Savings Optimizer endpoints."""
from __future__ import annotations


def test_health_ok(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root_metadata(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["optimize"].endswith("/savings/optimize")


def _valid_payload() -> dict:
    return {
        "currency": "INR",
        "monthly_salary": 220000,
        "monthly_expenses": 95000,
        "current_savings": 300000,
        "risk_profile": "moderate",
        "loans": [
            {"name": "Car Loan", "emi": 16000, "outstanding": 480000,
             "interest_rate_pct": 9.5, "months_remaining": 36},
        ],
        "goals": [
            {"name": "Emergency Fund", "target_amount": 800000, "saved_amount": 300000,
             "horizon_months": 12, "priority": "high"},
        ],
    }


def test_optimize_returns_full_plan(client):
    r = client.post("/api/v1/savings/optimize", json=_valid_payload())
    assert r.status_code == 200
    body = r.json()
    for key in (
        "emergency_fund", "recommended_monthly_saving", "recommended_sip",
        "recommended_fixed_deposit", "recommended_liquid_fund",
        "investment_allocation", "savings_score", "grade", "savings_rate_pct",
    ):
        assert key in body
    assert 0 <= body["savings_score"] <= 100
    assert body["grade"] in {"A", "B", "C", "D", "E"}
    assert body["emergency_fund"]["target"] > 0
    assert len(body["investment_allocation"]) == 3


def test_optimize_requires_salary(client):
    payload = _valid_payload()
    del payload["monthly_salary"]
    r = client.post("/api/v1/savings/optimize", json=payload)
    assert r.status_code == 422


def test_optimize_rejects_negative_salary(client):
    payload = _valid_payload()
    payload["monthly_salary"] = -5
    r = client.post("/api/v1/savings/optimize", json=payload)
    assert r.status_code == 422


def test_optimize_works_without_loans_or_goals(client):
    payload = _valid_payload()
    payload["loans"] = []
    payload["goals"] = []
    r = client.post("/api/v1/savings/optimize", json=payload)
    assert r.status_code == 200
    assert r.json()["total_emi"] == 0
