"""Concrete adapters implementing the domain ports."""
from advisor.repositories.deepseek_llm import DeepSeekLLMClient
from advisor.repositories.openbb_market_data import OpenBBMarketDataProvider
from advisor.repositories.rag_knowledge import RagKnowledgeRepository

__all__ = [
    "DeepSeekLLMClient",
    "OpenBBMarketDataProvider",
    "RagKnowledgeRepository",
]
