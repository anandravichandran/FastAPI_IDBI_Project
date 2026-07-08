"""ChromaDB vector-store adapter (production).

``chromadb`` is imported lazily so the package imports cheaply and can be
unit-tested without the dependency. A persistent client is used so the index
survives restarts. Cosine space is configured on the collection; Chroma returns
cosine *distance*, which we convert to a ``[0, 1]`` similarity score.
"""
from __future__ import annotations

import threading
from collections.abc import Sequence

from rag.core.exceptions import ConfigurationError, VectorStoreError
from rag.core.logging import get_logger
from rag.domain.entities import DocumentChunk, RetrievedChunk, Vector
from rag.domain.interfaces import IVectorStore

logger = get_logger(__name__)


class ChromaVectorStore(IVectorStore):
    def __init__(
        self,
        *,
        persist_dir: str = "./.chroma",
        collection_name: str = "documents",
    ) -> None:
        self._persist_dir = persist_dir
        self._collection_name = collection_name
        self._client = None
        self._collection = None
        self._lock = threading.RLock()

    def _ensure_collection(self):
        if self._collection is not None:
            return self._collection
        with self._lock:
            if self._collection is not None:
                return self._collection
            try:
                import chromadb  # type: ignore
            except ImportError as exc:  # pragma: no cover - environment dependent
                raise ConfigurationError(
                    "chromadb is not installed. Install it with "
                    "`pip install chromadb` or set VECTOR_BACKEND=memory."
                ) from exc
            logger.info(
                "Opening Chroma collection",
                extra={"path": self._persist_dir, "collection": self._collection_name},
            )
            self._client = chromadb.PersistentClient(path=self._persist_dir)
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            return self._collection

    def add(self, chunks: Sequence[DocumentChunk], embeddings: Sequence[Vector]) -> None:
        if len(chunks) != len(embeddings):
            raise VectorStoreError("chunks and embeddings length mismatch")
        if not chunks:
            return
        collection = self._ensure_collection()
        try:
            collection.upsert(
                ids=[c.chunk_id for c in chunks],
                embeddings=[list(e) for e in embeddings],
                documents=[c.text for c in chunks],
                metadatas=[c.as_metadata() for c in chunks],
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Chroma upsert failed")
            raise VectorStoreError("Failed to write to the vector store.") from exc

    def query(
        self,
        embedding: Vector,
        *,
        top_k: int,
        document_ids: Sequence[str] | None = None,
    ) -> list[RetrievedChunk]:
        collection = self._ensure_collection()
        where = {"document_id": {"$in": list(document_ids)}} if document_ids else None
        try:
            res = collection.query(
                query_embeddings=[list(embedding)],
                n_results=max(1, top_k),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Chroma query failed")
            raise VectorStoreError("Failed to query the vector store.") from exc

        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]

        results: list[RetrievedChunk] = []
        for cid, text, meta, dist in zip(ids, docs, metas, dists):
            meta = meta or {}
            # cosine distance -> cosine similarity in [0, 1]
            score = max(0.0, min(1.0, 1.0 - float(dist)))
            results.append(
                RetrievedChunk(
                    chunk_id=cid,
                    document_id=str(meta.get("document_id", "")),
                    filename=str(meta.get("filename", "")),
                    ordinal=int(meta.get("ordinal", 0)),
                    text=text or "",
                    score=round(score, 6),
                    metadata=dict(meta),
                )
            )
        return results

    def delete_document(self, document_id: str) -> int:
        collection = self._ensure_collection()
        try:
            existing = collection.get(where={"document_id": document_id})
            ids = existing.get("ids") or []
            if ids:
                collection.delete(ids=ids)
            return len(ids)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Chroma delete failed")
            raise VectorStoreError("Failed to delete from the vector store.") from exc

    def count(self) -> int:
        collection = self._ensure_collection()
        try:
            return int(collection.count())
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError("Failed to count the vector store.") from exc
