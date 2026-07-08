"""Abstract ports for the domain layer (Dependency Inversion).

The service layer depends only on these interfaces; concrete adapters live in
the repository layer and are injected at runtime.
"""
from coach.domain.interfaces.conversation import IConversationRepository
from coach.domain.interfaces.customer import ICustomerRepository
from coach.domain.interfaces.knowledge import IKnowledgeRepository
from coach.domain.interfaces.llm import ILLMClient

__all__ = [
    "IConversationRepository",
    "ICustomerRepository",
    "IKnowledgeRepository",
    "ILLMClient",
]
