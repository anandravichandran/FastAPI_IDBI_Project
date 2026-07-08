"""Abstract ports for the domain layer (Dependency Inversion).

The service layer depends only on these interfaces; concrete adapters live in
the repository layer and are injected at runtime by the composition root.
"""
from rag.domain.interfaces.document_parser import IDocumentParser
from rag.domain.interfaces.embedder import IEmbedder
from rag.domain.interfaces.registry import IDocumentRegistry
from rag.domain.interfaces.vector_store import IVectorStore

__all__ = [
    "IDocumentParser",
    "IEmbedder",
    "IDocumentRegistry",
    "IVectorStore",
]
