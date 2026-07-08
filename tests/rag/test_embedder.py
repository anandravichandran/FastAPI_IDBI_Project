"""Unit tests for the dependency-light HashingEmbedder."""
from __future__ import annotations

import math

from rag.repositories import HashingEmbedder


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def test_dimension_and_name() -> None:
    emb = HashingEmbedder(dimension=128)
    assert emb.dimension == 128
    assert "128" in emb.name


def test_deterministic_and_normalized() -> None:
    emb = HashingEmbedder(dimension=256)
    a = emb.embed_query("emergency fund savings")
    b = emb.embed_query("emergency fund savings")
    assert a == b
    assert abs(_norm(a) - 1.0) < 1e-6


def test_similar_text_scores_higher_than_unrelated() -> None:
    emb = HashingEmbedder(dimension=512)
    docs = emb.embed_documents(
        [
            "emergency fund covers unexpected expenses",
            "fixed deposit guaranteed interest rate",
        ]
    )
    q = emb.embed_query("how big should my emergency fund be")

    def cosine(x: list[float], y: list[float]) -> float:
        return sum(a * b for a, b in zip(x, y))

    assert cosine(q, docs[0]) > cosine(q, docs[1])


def test_empty_text_returns_zero_vector() -> None:
    emb = HashingEmbedder(dimension=64)
    assert emb.embed_query("") == [0.0] * 64
