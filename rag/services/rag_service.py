"""RAG use-case orchestration.

Coordinates the full pipeline behind the domain ports:

    ingest:   parse PDF → chunk → embed → store vectors → register catalog
    retrieve: embed query → similarity search → filter by relevance
    context:  assemble retrieved chunks into grounded, budget-limited context
              and a DeepSeek-ready ``messages=[...]`` payload

The service is synchronous and pure of framework concerns; the API layer runs
its CPU-bound methods in a worker thread. It depends only on the abstract
ports, so any adapter (Sentence Transformers / hashing, ChromaDB / in-memory)
can be injected.
"""
from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence

from rag.core.config import Settings
from rag.core.exceptions import (
    DocumentNotFoundError,
    DocumentProcessingError,
    DomainValidationError,
    PayloadTooLargeError,
)
from rag.core.logging import get_logger
from rag.domain.entities import (
    Document,
    PromptMessage,
    RagContext,
    RetrievalResult,
    RetrievedChunk,
)
from rag.domain.enums import DocumentStatus
from rag.domain.interfaces import (
    IDocumentParser,
    IDocumentRegistry,
    IEmbedder,
    IVectorStore,
)
from rag.services.chunking import TextChunker

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a financial assistant. Answer the user's question using ONLY the "
    "context provided below. If the context does not contain the answer, say you "
    "don't have enough information. Cite the source filename in parentheses when "
    "you use a fact."
)


class RagService:
    def __init__(
        self,
        *,
        parser: IDocumentParser,
        chunker: TextChunker,
        embedder: IEmbedder,
        vector_store: IVectorStore,
        registry: IDocumentRegistry,
        settings: Settings,
    ) -> None:
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._store = vector_store
        self._registry = registry
        self._settings = settings

    # -- ingestion ---------------------------------------------------------
    def ingest_pdf(self, *, filename: str, data: bytes) -> Document:
        """Parse, chunk, embed and index a PDF; return its catalog record."""
        if not filename:
            raise DomainValidationError("A filename is required.")
        if not data:
            raise DocumentProcessingError("Uploaded file is empty.")
        if len(data) > self._settings.max_upload_bytes:
            raise PayloadTooLargeError(
                f"File exceeds the {self._settings.max_upload_mb} MB limit.",
                details={"size_bytes": len(data)},
            )

        document_id = uuid.uuid4().hex
        created_at = dt.datetime.now(tz=dt.timezone.utc).isoformat()
        logger.info(
            "Ingesting document",
            extra={"document_id": document_id, "filename": filename},
        )

        try:
            parsed = self._parser.parse(
                document_id=document_id, filename=filename, data=data
            )
            chunks = self._chunker.split(
                document_id=document_id, filename=filename, text=parsed.text
            )
            if not chunks:
                raise DocumentProcessingError(
                    "Document produced no chunks after processing."
                )
            embeddings = self._embedder.embed_documents([c.text for c in chunks])
            self._store.add(chunks, embeddings)
        except Exception as exc:
            failed = Document(
                document_id=document_id,
                filename=filename,
                status=DocumentStatus.FAILED,
                page_count=0,
                chunk_count=0,
                char_count=len(data),
                created_at=created_at,
                error=str(exc),
            )
            self._registry.save(failed)
            raise

        document = Document(
            document_id=document_id,
            filename=filename,
            status=DocumentStatus.INDEXED,
            page_count=parsed.page_count,
            chunk_count=len(chunks),
            char_count=parsed.char_count,
            created_at=created_at,
        )
        self._registry.save(document)
        logger.info(
            "Document indexed",
            extra={
                "document_id": document_id,
                "chunks": len(chunks),
                "pages": parsed.page_count,
            },
        )
        return document

    # -- retrieval ---------------------------------------------------------
    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        document_ids: Sequence[str] | None = None,
    ) -> RetrievalResult:
        """Return the chunks most relevant to ``query``."""
        cleaned = (query or "").strip()
        if not cleaned:
            raise DomainValidationError("Query must not be empty.")

        k = self._resolve_top_k(top_k)
        query_vec = self._embedder.embed_query(cleaned)
        hits = self._store.query(query_vec, top_k=k, document_ids=document_ids)
        threshold = self._settings.min_relevance_score
        if threshold > 0:
            hits = [h for h in hits if h.score >= threshold]
        return RetrievalResult(
            query=cleaned,
            chunks=tuple(hits),
            embedding_backend=self._embedder.name,
            vector_backend=type(self._store).__name__,
        )

    # -- context assembly for DeepSeek ------------------------------------
    def build_context(
        self,
        query: str,
        *,
        top_k: int | None = None,
        document_ids: Sequence[str] | None = None,
    ) -> RagContext:
        """Retrieve, then assemble a grounded, budget-limited context block and a
        DeepSeek-ready chat payload."""
        result = self.retrieve(query, top_k=top_k, document_ids=document_ids)
        context, used, truncated = self._assemble_context(result.chunks)

        user_content = (
            f"Context:\n{context}\n\nQuestion: {result.query}"
            if context
            else f"Question: {result.query}\n\n(No relevant context was found.)"
        )
        messages = (
            PromptMessage(role="system", content=_SYSTEM_PROMPT),
            PromptMessage(role="user", content=user_content),
        )
        approx_tokens = self._estimate_tokens(_SYSTEM_PROMPT) + self._estimate_tokens(
            user_content
        )
        return RagContext(
            query=result.query,
            context=context,
            chunks=used,
            messages=messages,
            approx_tokens=approx_tokens,
            truncated=truncated,
        )

    # -- catalog -----------------------------------------------------------
    def list_documents(self) -> list[Document]:
        return self._registry.list()

    def get_document(self, document_id: str) -> Document:
        doc = self._registry.get(document_id)
        if doc is None:
            raise DocumentNotFoundError(
                "No document with that id.", details={"document_id": document_id}
            )
        return doc

    def delete_document(self, document_id: str) -> int:
        doc = self._registry.get(document_id)
        if doc is None:
            raise DocumentNotFoundError(
                "No document with that id.", details={"document_id": document_id}
            )
        deleted = self._store.delete_document(document_id)
        self._registry.delete(document_id)
        logger.info(
            "Document deleted",
            extra={"document_id": document_id, "chunks_removed": deleted},
        )
        return deleted

    def stats(self) -> dict[str, object]:
        docs = self._registry.list()
        return {
            "documents": len(docs),
            "chunks": self._store.count(),
            "embedding_model": self._embedder.name,
            "embedding_dim": self._embedder.dimension,
            "vector_store": type(self._store).__name__,
        }

    # -- internals ---------------------------------------------------------
    def _resolve_top_k(self, top_k: int | None) -> int:
        if top_k is None:
            return self._settings.default_top_k
        if top_k < 1:
            raise DomainValidationError("top_k must be >= 1.")
        return min(top_k, self._settings.max_top_k)

    def _assemble_context(
        self, chunks: Sequence[RetrievedChunk]
    ) -> tuple[str, tuple[RetrievedChunk, ...], bool]:
        budget = self._settings.max_context_chars
        sep = self._settings.context_separator
        blocks: list[str] = []
        used: list[RetrievedChunk] = []
        length = 0
        truncated = False
        for chunk in chunks:
            block = f"[Source: {chunk.filename} #{chunk.ordinal}]\n{chunk.text}"
            addition = len(block) + (len(sep) if blocks else 0)
            if length + addition > budget:
                if not blocks:
                    # First chunk already exceeds the budget: include a hard cut.
                    blocks.append(block[:budget])
                    used.append(chunk)
                truncated = True
                break
            blocks.append(block)
            used.append(chunk)
            length += addition
        return sep.join(blocks), tuple(used), truncated

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        # Rough heuristic: ~4 characters per token.
        return max(1, len(text) // 4)
