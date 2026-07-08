"""Shared test fixtures.

Everything runs fully offline: the LLM port is replaced by a fake so tests
never touch the network, and the in-memory repositories provide seed data.
"""
from __future__ import annotations

from collections.abc import Sequence

import pytest
from fastapi.testclient import TestClient

from coach.api import deps
from coach.core.config import Settings
from coach.domain.entities import LLMMessage, LLMResult
from coach.domain.interfaces import ILLMClient
from coach.main import create_app
from coach.repositories import (
    InMemoryConversationRepository,
    InMemoryCustomerRepository,
    RagKnowledgeRepository,
)
from coach.services import (
    AffordabilityEngine,
    CoachService,
    FinancialAnalyzer,
    IntentClassifier,
    PromptBuilder,
)


class FakeLLM(ILLMClient):
    """Deterministic LLM stand-in that echoes a valid JSON narration."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, messages: Sequence[LLMMessage], *, json_mode: bool = False) -> LLMResult:
        self.calls += 1
        content = (
            '{"reply": "Here is my take.", "detail": "Grounded explanation.", '
            '"avatar_speech": "Let me help!", "emotion": "encouraging", '
            '"action_items": ["Do the thing"], "quick_replies": ["Tell me more"]}'
        )
        return LLMResult(content=content, model="fake-deepseek", finish_reason="stop")


@pytest.fixture
def settings() -> Settings:
    # No API key -> service uses deterministic fallback unless we inject FakeLLM.
    return Settings(deepseek_api_key=None, log_json=False, rag_top_k=3)


@pytest.fixture
def analyzer(settings: Settings) -> FinancialAnalyzer:
    return FinancialAnalyzer(settings)


@pytest.fixture
def coach_service(settings: Settings) -> CoachService:
    return CoachService(
        settings=settings,
        customers=InMemoryCustomerRepository(),
        knowledge=RagKnowledgeRepository(settings),
        conversations=InMemoryConversationRepository(),
        llm=FakeLLM(),
        analyzer=FinancialAnalyzer(settings),
        affordability=AffordabilityEngine(settings),
        intent_classifier=IntentClassifier(),
        prompt_builder=PromptBuilder(),
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    """TestClient with a FakeLLM injected via dependency override."""
    app = create_app(settings)
    fake = FakeLLM()
    coach.dependency_overrides[deps.get_llm_client] = lambda: fake
    coach.dependency_overrides[deps.get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
