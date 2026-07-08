"""End-to-end API tests via FastAPI TestClient (synthetic backend).

Skipped automatically if FastAPI/starlette test deps are unavailable so the
suite still collects in a minimal environment.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from market.core.config import Settings, get_settings  # noqa: E402
from market.main import create_app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    settings = Settings(provider_backend="synthetic", rate_limit_enabled=False)
    app = create_app(settings)
    # Ensure deps use the synthetic backend too.
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["provider"] == "synthetic"


def test_stock_quote(client):
    r = client.get("/api/v1/stocks/AAPL/quote")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "AAPL"
    assert body["asset_class"] == "stock"
    assert body["price"] > 0


def test_stock_historical(client):
    r = client.get("/api/v1/stocks/AAPL/historical?limit=15")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 15
    assert len(body["points"]) == 15


def test_stock_ratios(client):
    r = client.get("/api/v1/stocks/AAPL/ratios")
    assert r.status_code == 200
    assert r.json()["pe_ratio"] is not None


def test_mutual_fund_and_etf(client):
    assert client.get("/api/v1/mutual-funds/VFIAX").status_code == 200
    assert client.get("/api/v1/etf/SPY").status_code == 200


def test_gold(client):
    r = client.get("/api/v1/gold")
    assert r.status_code == 200
    assert r.json()["asset_class"] == "gold"


def test_index(client):
    r = client.get("/api/v1/indices/%5EGSPC")
    assert r.status_code == 200
    assert r.json()["asset_class"] == "index"


def test_news_get_and_post(client):
    r = client.get("/api/v1/news?symbols=AAPL&limit=3")
    assert r.status_code == 200
    assert r.json()["count"] == 3
    r2 = client.post("/api/v1/news", json={"query": "inflation", "limit": 4})
    assert r2.status_code == 200
    assert r2.json()["count"] == 4


def test_unknown_symbol_returns_404(client):
    r = client.get("/api/v1/stocks/UNKNOWN/quote")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "symbol_not_found"


def test_cache_stats_endpoint(client):
    client.get("/api/v1/stocks/AAPL/quote")
    r = client.get("/api/v1/cache/stats")
    assert r.status_code == 200
    assert "hit_rate" in r.json()
