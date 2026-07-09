"""Dependency-injection composition root.

This is the single place where concrete adapters are wired to the abstract
ports the service layer depends on. FastAPI's ``Depends`` resolves the graph
per-request, while stateful singletons (settings, repositories, LLM client)
are cached for the process lifetime. Swapping an adapter (e.g. a real
core-banking client or a vector DB) only requires editing this file.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from coach.core.config import Settings, get_settings
from coach.domain.interfaces import (
    IConversationRepository,
    ICustomerRepository,
    IKnowledgeRepository,
    ILLMClient,
)
from coach.repositories import (
    DeepSeekLLMClient,
    InMemoryConversationRepository,
    InMemoryCustomerRepository,
    NvidiaLLMClient,
    RagKnowledgeRepository,
)
from coach.services import (
    AffordabilityEngine,
    CoachService,
    FinancialAnalyzer,
    IntentClassifier,
    PromptBuilder,
)

SettingsDep = Annotated[Settings, Depends(get_settings)]


# --- Singletons (process-lifetime) ------------------------------------------
@lru_cache
def get_customer_repository() -> ICustomerRepository:
    return InMemoryCustomerRepository()


@lru_cache
def get_conversation_repository() -> IConversationRepository:
    return InMemoryConversationRepository()


@lru_cache
def get_knowledge_repository() -> IKnowledgeRepository:
    return RagKnowledgeRepository(get_settings())


@lru_cache
def get_llm_client() -> ILLMClient:
    settings = get_settings()
    if settings.llm_provider == "nvidia":
        return NvidiaLLMClient(settings)
    return DeepSeekLLMClient(settings)


@lru_cache
def get_analyzer() -> FinancialAnalyzer:
    return FinancialAnalyzer(get_settings())


@lru_cache
def get_affordability_engine() -> AffordabilityEngine:
    return AffordabilityEngine(get_settings())


@lru_cache
def get_intent_classifier() -> IntentClassifier:
    return IntentClassifier()


@lru_cache
def get_prompt_builder() -> PromptBuilder:
    return PromptBuilder()


# --- Aggregate use-case service ---------------------------------------------
def get_coach_service(
    settings: SettingsDep,
    customers: Annotated[ICustomerRepository, Depends(get_customer_repository)],
    knowledge: Annotated[IKnowledgeRepository, Depends(get_knowledge_repository)],
    conversations: Annotated[IConversationRepository, Depends(get_conversation_repository)],
    llm: Annotated[ILLMClient, Depends(get_llm_client)],
    analyzer: Annotated[FinancialAnalyzer, Depends(get_analyzer)],
    affordability: Annotated[AffordabilityEngine, Depends(get_affordability_engine)],
    intents: Annotated[IntentClassifier, Depends(get_intent_classifier)],
    prompts: Annotated[PromptBuilder, Depends(get_prompt_builder)],
) -> CoachService:
    return CoachService(
        settings=settings,
        customers=customers,
        knowledge=knowledge,
        conversations=conversations,
        llm=llm,
        analyzer=analyzer,
        affordability=affordability,
        intent_classifier=intents,
        prompt_builder=prompts,
    )


CoachServiceDep = Annotated[CoachService, Depends(get_coach_service)]


async def shutdown_dependencies() -> None:
    """Release process-lifetime resources on application shutdown."""
    llm = get_llm_client()
    await llm.aclose()
