"""Production-grade Retrieval-Augmented Generation (RAG) microservice.

Upload PDFs → chunk → embed (Sentence Transformers) → store (ChromaDB) →
retrieve relevant chunks → return grounded context ready for DeepSeek V3.

Built as a self-contained Clean Architecture application (API → Services →
Domain ports ← Repositories) and mounted in the Financial Suite at ``/rag``.
"""

__all__: list[str] = []
