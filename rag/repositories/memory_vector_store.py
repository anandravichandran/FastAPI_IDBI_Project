"""In-memory cosine vector store (dependency-light).

Used for tests and air-gapped environments. Keeps chunks and their embeddings
in process memory and answers similarity queries with brute-force cosine
similarity. Not persistent; swap for :class:`ChromaVectorStore` in production.
"""
from __future__ import annotations

import math
import threading
from collections.abc import Sequence

from rag.core.exceptions import VectorStoreError
from rag.domain.entities import DocumentChunk, RetrievedChunk, Vector
from rag.domain.interfaces import IVectorStore


class _Record:
    __slots__ = ("chunk", "vector", "norm")

    def __init__(self, chunk: DocumentChunk, vector: Vector) -> None:
        self.chunk = chunk
        self.vector = vector
        self.norm = math.sqrt(sum(v * v for v in vector))


class InMemoryVectorStore(IVectorStore):
    def __init__(self) -> None:
        self._records: dict[str, _Record] = {}
        self._lock = threading.RLock()

    def add(self, chunks: Sequence[DocumentChunk], embeddings: Sequence[Vector]) -> None:
        if len(chunks) != len(embeddings):
            raise VectorStoreError("chunks and embeddings length mismatch")
        with self._lock:
            for chunk, vector in zip(chunks, embeddings):
                self._records[chunk.chunk_id] = _Record(chunk, list(vector))

    def query(
        self,
        embedding: Vector,
        *,
        top_k: int,
        document_ids: Sequence[str] | None = None,
    ) -> list[RetrievedChunk]:
        q_norm = math.sqrt(sum(v * v for v in embedding))
        if q_norm == 0:
            return []
        allowed = set(document_ids) if document_ids else None
        scored: list[tuple[float, DocumentChunk]] = []
        with self._lock:
            records = list(self._records.values())
        for rec in records:
            if allowed is not None and rec.chunk.document_id not in allowed:
                continue
            if rec.norm == 0:
                continue
            dot = sum(a * b for a, b in zip(embedding, rec.vector))
            score = dot / (q_norm * rec.norm)
            scored.append((score, rec.chunk))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        results: list[RetrievedChunk] = []
        for score, chunk in scored[: max(0, top_k)]:
            # Map cosine [-1, 1] to [0, 1] for a stable, client-friendly score.
            normalised = max(0.0, min(1.0, (score + 1.0) / 2.0))
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    filename=chunk.filename,
                    ordinal=chunk.ordinal,
                    text=chunk.text,
                    score=round(normalised, 6),
                    metadata=dict(chunk.metadata),
                )
            )
        return results

    def delete_document(self, document_id: str) -> int:
        with self._lock:
            to_remove = [
                cid for cid, rec in self._records.items()
                if rec.chunk.document_id == document_id
            ]
            for cid in to_remove:
                del self._records[cid]
        return len(to_remove)

    def count(self) -> int:
        with self._lock:
            return len(self._records)
