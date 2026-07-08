"""In-memory document catalog adapter.

Tracks ingested-document metadata and lifecycle status. Thread-safe and
ordered most-recent-first. Swap for a relational-database adapter in production
without touching the service layer.
"""
from __future__ import annotations

import threading

from rag.domain.entities import Document
from rag.domain.interfaces import IDocumentRegistry


class InMemoryDocumentRegistry(IDocumentRegistry):
    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def save(self, document: Document) -> None:
        with self._lock:
            if document.document_id not in self._docs:
                self._order.append(document.document_id)
            self._docs[document.document_id] = document

    def get(self, document_id: str) -> Document | None:
        with self._lock:
            return self._docs.get(document_id)

    def list(self) -> list[Document]:
        with self._lock:
            return [self._docs[d] for d in reversed(self._order) if d in self._docs]

    def delete(self, document_id: str) -> bool:
        with self._lock:
            if document_id not in self._docs:
                return False
            del self._docs[document_id]
            self._order = [d for d in self._order if d != document_id]
            return True
