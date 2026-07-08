"""Concrete adapters implementing the domain ports."""
from coach.repositories.conversation_repository import InMemoryConversationRepository
from coach.repositories.customer_repository import InMemoryCustomerRepository
from coach.repositories.deepseek_llm import DeepSeekLLMClient
from coach.repositories.rag_knowledge import RagKnowledgeRepository

__all__ = [
    "InMemoryConversationRepository",
    "InMemoryCustomerRepository",
    "DeepSeekLLMClient",
    "RagKnowledgeRepository",
]
