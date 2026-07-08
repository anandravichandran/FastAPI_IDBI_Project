"""Unit tests for the in-memory cosine vector store."""
from __future__ import annotations

from rag.domain.entities import DocumentChunk
from rag.repositories import HashingEmbedder, InMemoryVectorStore


def _chunk(cid: str, doc: str, ordinal: int, text: str) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=cid,
        document_id=doc,
        filename="f.pdf",
        ordinal=ordinal,
        text=text,
        start_char=0,
        end_char=len(text),
    )


def test_add_query_and_scores_are_ranked() -> None:
    emb = HashingEmbedder(dimension=512)
    store = InMemoryVectorStore()
    chunks = [
        _chunk("c0", "d1", 0, "emergency fund for unexpected expenses"),
        _chunk("c1", "d1", 1, "fixed deposit locked term interest"),
    ]
    store.add(chunks, emb.embed_documents([c.text for c in chunks]))
    assert store.count() == 2

    hits = store.query(emb.embed_query("emergency fund size"), top_k=2)
    assert len(hits) == 2
    assert hits[0].chunk_id == "c0"
    assert hits[0].score >= hits[1].score
    assert 0.0 <= hits[0].score <= 1.0


def test_document_filter_and_delete() -> None:
    emb = HashingEmbedder(dimension=256)
    store = InMemoryVectorStore()
    chunks = [
        _chunk("a0", "da", 0, "savings rate percentage"),
        _chunk("b0", "db", 0, "savings rate percentage"),
    ]
    store.add(chunks, emb.embed_documents([c.text for c in chunks]))

    only_a = store.query(emb.embed_query("savings"), top_k=5, document_ids=["da"])
    assert {h.document_id for h in only_a} == {"da"}

    removed = store.delete_document("da")
    assert removed == 1
    assert store.count() == 1
