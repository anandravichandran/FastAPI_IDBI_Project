"""API-level tests for the Budget Planner endpoints."""
from __future__ import annotations


def test_health_ok(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root_metadata(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["plan"].endswith("/budget/plan")


def _valid_payload() -> dict:
    return {
        "currency": "INR",
        "incomes": [{"name": "Salary", "amount": 220000, "frequency": "monthly"}],
        "expenses": [
            {"category": "groceries", "amount": 18000},
            {"category": "dining_out", "amount": 12000},
            {"category": "shopping", "amount": 15000},
        ],
        "bills": [
            {"name": "Rent", "amount": 45000, "category": "housing", "due_day": 5},
            {"name": "Car EMI", "amount": 16000, "category": "loan_emi", "autopay": True},
        ],
        "goals": [
            {"name": "Emergency Fund", "target_amount": 600000, "saved_amount": 150000,
             "months_remaining": 18, "priority": "high"},
        ],
    }


def test_plan_returns_full_budget(client):
    r = client.post("/api/v1/budget/plan", json=_valid_payload())
    assert r.status_code == 200
    body = r.json()
    # Contract: every required output section is present.
    for key in (
        "recommended_budget", "expense_breakdown", "savings_pct", "alerts",
        "overspending", "budget_score", "grade", "buckets", "goals",
    ):
        assert key in body
    assert 0 <= body["budget_score"] <= 100
    assert body["grade"] in {"A", "B", "C", "D", "E"}
    assert body["monthly_income"] == 220000


def test_plan_requires_income(client):
    payload = _valid_payload()
    payload["incomes"] = []
    r = client.post("/api/v1/budget/plan", json=payload)
    assert r.status_code == 422  # pydantic min_length violation


def test_plan_rejects_unknown_category(client):
    payload = _valid_payload()
    payload["expenses"][0]["category"] = "crypto_moon"
    r = client.post("/api/v1/budget/plan", json=payload)
    assert r.status_code == 422
