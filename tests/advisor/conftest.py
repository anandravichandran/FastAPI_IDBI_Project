"""Shared test fixtures.

Provides a fully in-memory application with fake adapters so the suite runs
offline (no OpenBB, no DeepSeek, no network).
"""
from __future__ import annotations

from collections.abc import Sequence

import pytest
from fastapi.testclient import TestClient

from advisor.api import deps
from advisor.core.config import Settings
from advisor.domain.entities import (
    KnowledgeSnippet,
    LLMMessage,
    LLMResult,
    MarketQuote,
    MarketSnapshot,
)
from advisor.domain.interfaces.knowledge import IKnowledgeRepository
from advisor.domain.interfaces.llm import ILLMClient
from advisor.domain.interfaces.market_data import IMarketDataProvider
from advisor.main import create_app
from advisor.services.advisor_service import AdvisorService
from advisor.services.portfolio_analyzer import PortfolioAnalyzer
from advisor.services.prompt_builder import PromptBuilder


class FakeMarketData(IMarketDataProvider):
    async def get_snapshot(self, symbols: Sequence[str]) -> MarketSnapshot:
        return MarketSnapshot(
            quotes=[MarketQuote(symbol=s, price=100.0, change_percent_1d=0.5) for s in symbols],
            source="fake",
        )


class FakeKnowledge(IKnowledgeRepository):
    async def retrieve(self, query: str, *, top_k: int) -> list[KnowledgeSnippet]:
        return [
            KnowledgeSnippet(
                id="kb-test", title="Test", content="Diversify and rebalance.", score=1.0
            )
        ]


class FakeLLM(ILLMClient):
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def complete(self, messages: Sequence[LLMMessage], *, json_mode: bool = False) -> LLMResult:
        if self.fail:
            from advisor.core.exceptions import LLMError

            raise LLMError("boom")
        return LLMResult(
            content='{"explanation": "Test explanation.", '
            '"diversification_recommendations": ["Add bonds."]}',
            model="deepseek-chat",
        )


@pytest.fixture
def settings() -> Settings:
    return Settings(deepseek_api_key="test-key", log_json=False, environment="local")


@pytest.fixture
def analyzer(settings: Settings) -> PortfolioAnalyzer:
    return PortfolioAnalyzer(settings)


@pytest.fixture
def make_service(settings: Settings, analyzer: PortfolioAnalyzer):
    def _make(*, llm_fail: bool = False) -> AdvisorService:
        return AdvisorService(
            settings=settings,
            analyzer=analyzer,
            prompt_builder=PromptBuilder(),
            market_data=FakeMarketData(),
            knowledge=FakeKnowledge(),
            llm=FakeLLM(fail=llm_fail),
        )

    return _make


@pytest.fixture
def client(settings: Settings, make_service):
    app = create_app(settings)
    app.dependency_overrides[deps.get_advisor_service] = lambda: make_service()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_payload() -> dict:
    return {
        "user_profile": {
            "full_name": "Ada Lovelace",
            "age": 34,
            "dependents": 1,
            "country": "IN",
            "currency": "INR",
            "employment_status": "salaried",
        },
        "risk_profile": {
            "tolerance": "moderate",
            "investment_horizon_years": 15,
            "max_drawdown_tolerance_pct": 25.0,
            "has_stable_income": True,
        },
        "monthly_income": 250000,
        "monthly_expenses": 120000,
        "current_savings": 500000,
        "goals": [
            {"name": "Retirement", "target_amount": 20000000, "priority": "high"}
        ],
        "current_portfolio": [
            {"symbol": "SPY", "asset_class": "equity", "current_value": 800000},
            {"symbol": "AGG", "asset_class": "fixed_income", "current_value": 200000},
        ],
    }
