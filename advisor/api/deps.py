"""Dependency-injection wiring.

Composition root for the application. Concrete adapters are constructed here
and injected into the service layer through the domain interfaces, so the rest
of the codebase depends on abstractions only (Dependency Inversion).

Singletons are cached with ``lru_cache`` keyed on the settings object; FastAPI
``Depends`` resolves them per request without rebuilding.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from advisor.core.config import Settings, get_settings
from advisor.domain.interfaces.knowledge import IKnowledgeRepository
from advisor.domain.interfaces.llm import ILLMClient
from advisor.domain.interfaces.market_data import IMarketDataProvider
from advisor.repositories.deepseek_llm import DeepSeekLLMClient
from advisor.repositories.openbb_market_data import OpenBBMarketDataProvider
from advisor.repositories.rag_knowledge import RagKnowledgeRepository
from advisor.services.advisor_service import AdvisorService
from advisor.services.portfolio_analyzer import PortfolioAnalyzer
from advisor.services.prompt_builder import PromptBuilder

SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache
def get_market_data_provider(settings: Settings) -> IMarketDataProvider:
    return OpenBBMarketDataProvider(settings)


@lru_cache
def get_knowledge_repository(settings: Settings) -> IKnowledgeRepository:
    return RagKnowledgeRepository(settings)


@lru_cache
def get_llm_client(settings: Settings) -> ILLMClient:
    return DeepSeekLLMClient(settings)


@lru_cache
def get_analyzer(settings: Settings) -> PortfolioAnalyzer:
    return PortfolioAnalyzer(settings)


@lru_cache
def get_prompt_builder() -> PromptBuilder:
    return PromptBuilder()


def get_advisor_service(settings: SettingsDep) -> AdvisorService:
    """Assemble the fully-wired :class:`AdvisorService`."""
    return AdvisorService(
        settings=settings,
        analyzer=get_analyzer(settings),
        prompt_builder=get_prompt_builder(),
        market_data=get_market_data_provider(settings),
        knowledge=get_knowledge_repository(settings),
        llm=get_llm_client(settings),
    )


AdvisorServiceDep = Annotated[AdvisorService, Depends(get_advisor_service)]


async def shutdown_dependencies() -> None:
    """Release pooled resources held by cached singletons."""
    settings = get_settings()
    llm = get_llm_client(settings)
    await llm.aclose()
