"""End-to-end API tests for the coach endpoints."""
from __future__ import annotations

import pytest

_QUESTIONS = [
    ("Can I buy a car worth 12 lakh?", "buy_car"),
    ("Should I increase my SIP?", "increase_sip"),
    ("Can I afford a home loan of 80 lakh?", "home_loan"),
    ("Am I overspending?", "overspending"),
    ("How can I improve my savings?", "improve_savings"),
]


@pytest.mark.parametrize("message, expected_intent", _QUESTIONS)
def test_chat_intents(client, message, expected_intent):
    resp = client.post(
        "/api/v1/coach/chat",
        json={"customer_id": "cust-001", "message": message},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["intent"] == expected_intent
    assert body["verdict"] in {"yes", "caution", "no", "info"}
    assert body["reply"]
    assert body["avatar"]["speech"]
    assert body["avatar"]["emotion"] in {
        "happy", "encouraging", "neutral", "concerned", "celebrating"
    }
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["llm_used"] is True
    assert body["llm_model"] == "fake-deepseek"
    assert isinstance(body["sources"], list) and body["sources"]
    assert resp.headers.get("X-Request-ID")


def test_chat_creates_and_returns_history():
    # Uses its own client to isolate history state.
    from coach.api import deps
    from coach.core.config import Settings
    from coach.main import create_app
    from fastapi.testclient import TestClient
    from tests.coach.conftest import FakeLLM

    settings = Settings(deepseek_api_key=None, log_json=False)
    app = create_app(settings)
    coach.dependency_overrides[deps.get_llm_client] = lambda: FakeLLM()
    # Fresh conversation store for this app instance.
    from coach.repositories import InMemoryConversationRepository
    store = InMemoryConversationRepository()
    coach.dependency_overrides[deps.get_conversation_repository] = lambda: store

    with TestClient(app) as client:
        chat = client.post(
            "/api/v1/coach/chat",
            json={"customer_id": "cust-001", "message": "Am I overspending?"},
        ).json()
        session_id = chat["session_id"]

        hist = client.get(
            "/api/v1/coach/history",
            params={"customer_id": "cust-001", "session_id": session_id},
        )
        assert hist.status_code == 200
        body = hist.json()
        # One user + one coach turn were persisted.
        assert body["count"] == 2
        assert body["turns"][0]["role"] == "user"
        assert body["turns"][1]["role"] == "coach"


def test_summary_endpoint(client):
    resp = client.get("/api/v1/coach/summary", params={"customer_id": "cust-001"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["customer_id"] == "cust-001"
    assert 0 <= body["financial_health_score"] <= 100
    assert body["health_grade"] in {"A", "B", "C", "D", "E"}
    assert body["monthly_income"] > 0
    assert isinstance(body["goals"], list) and body["goals"]
    assert isinstance(body["recommendations"], list) and body["recommendations"]


def test_unknown_customer_returns_404(client):
    resp = client.get("/api/v1/coach/summary", params={"customer_id": "nope"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "customer_not_found"


def test_chat_validation_error(client):
    resp = client.post("/api/v1/coach/chat", json={"customer_id": "cust-001"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "request_validation_error"
