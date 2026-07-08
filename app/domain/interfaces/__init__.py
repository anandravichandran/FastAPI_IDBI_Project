"""Abstract ports for the domain layer (Dependency Inversion).

The service layer depends only on these interfaces; concrete adapters live in
the repository layer and are injected at runtime.
"""
from app.domain.interfaces.knowledge import IKnowledgeRepository
from app.domain.interfaces.llm import ILLMClient
from app.domain.interfaces.market_data import IMarketDataProvider

__all__ = [
    "IKnowledgeRepository",
    "ILLMClient",
    "IMarketDataProvider",
]
