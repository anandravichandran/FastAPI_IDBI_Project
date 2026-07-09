"""End-to-end API tests for the advisor endpoint."""
from __future__ import annotations


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["llm_configured"] is True


def test_advice_happy_path(client, sample_payload):
    resp = client.post("/api/v1/advisor/advice", json=sample_payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["llm_used"] is True
    assert body["explanation"] == "Test explanation."
    assert 0 <= body["risk_score"]["score"] <= 100
    assert body["portfolio_analysis"]["total_value"] == 1000000.0
    assert body["emergency_fund"]["recommended_amount"] > 0
    assert body["sip_recommendation"]["recommended_monthly_amount"] >= 0
    assert body["asset_allocation"]["target"]
    assert "X-Request-ID" in resp.headers
    # LLM diversification recommendation is merged in.
    assert "Add bonds." in body["diversification"]["recommendations"]


def test_advice_validation_error(client, sample_payload):
    sample_payload["user_profile"]["age"] = 5  # below minimum
    resp = client.post("/api/v1/advisor/advice", json=sample_payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "request_validation_error"


def test_advice_falls_back_without_llm(settings, make_service, sample_payload):
    from advisor.api import deps
    from advisor.main import create_app
    from fastapi.testclient import TestClient

    app = create_app(settings)
    app.dependency_overrides[deps.get_advisor_service] = lambda: make_service(llm_fail=True)
    with TestClient(app) as client:
        resp = client.post("/api/v1/advisor/advice", json=sample_payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["llm_used"] is False
    assert body["llm_model"] == "deterministic-fallback"
    assert body["explanation"]
