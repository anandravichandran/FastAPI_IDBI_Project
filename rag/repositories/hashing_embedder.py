"""Dependency-light, deterministic embedding adapter.

A feature-hashing bag-of-words embedder used for tests and air-gapped
environments where Sentence Transformers is not installed. It produces stable,
L2-normalised vectors so cosine similarity is meaningful for keyword overlap —
enough to exercise the full ingest → retrieve pipeline offline. Not intended to
replace a real semantic model in production.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Sequence

from rag.domain.entities import Vector
from rag.domain.interfaces import IEmbedder

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashingEmbedder(IEmbedder):
    def __init__(self, *, dimension: int = 384) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension

    @property
    def name(self) -> str:
        return f"hashing-bow-{self._dimension}"

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> Vector:
        return self._embed(text)

    # -- internals ---------------------------------------------------------
    def _embed(self, text: str) -> Vector:
        vec = [0.0] * self._dimension
        tokens = _TOKEN_RE.findall((text or "").lower())
        if not tokens:
            return vec
        counts = Counter(tokens)
        for token, count in counts.items():
            bucket, sign = self._hash(token)
            # Sub-linear term weighting damps very frequent tokens.
            vec[bucket] += sign * (1.0 + math.log(count))
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def _hash(self, token: str) -> tuple[int, float]:
        digest = hashlib.md5(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "little") % self._dimension
        sign = 1.0 if digest[4] & 1 else -1.0
        return bucket, sign
