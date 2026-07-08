"""Abstract ports for the domain layer (Dependency Inversion).

The service layer depends only on these interfaces; concrete adapters live in
the repository layer and are injected at runtime.
"""
from advisor.domain.interfaces.knowledge import IKnowledgeRepository
from advisor.domain.interfaces.llm import ILLMClient
from advisor.domain.interfaces.market_data import IMarketDataProvider

__all__ = [
    "IKnowledgeRepository",
    "ILLMClient",
    "IMarketDataProvider",
]
