"""RAG knowledge repository.

Implements :class:`IKnowledgeRepository` with a dependency-light retrieval
engine over a curated corpus of financial-planning principles. Retrieval uses
a TF-IDF + cosine-similarity ranker so it works fully offline; the same
interface can later be backed by a vector database without touching callers.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
from collections import Counter
from pathlib import Path

from advisor.core.config import Settings
from advisor.core.logging import get_logger
from advisor.domain.entities import KnowledgeSnippet
from advisor.domain.interfaces.knowledge import IKnowledgeRepository

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_DEFAULT_CORPUS: list[dict[str, str]] = [
    {
        "id": "kb-emergency-fund",
        "title": "Emergency fund sizing",
        "content": (
            "An emergency fund should cover three to six months of essential "
            "living expenses. Households with a single income, variable pay, or "
            "dependents should target the higher end (six to twelve months). "
            "Hold it in liquid, capital-stable instruments such as a high-yield "
            "savings account or liquid/overnight funds, not in equities."
        ),
    },
    {
        "id": "kb-asset-allocation",
        "title": "Age and risk based asset allocation",
        "content": (
            "Asset allocation is the primary driver of long-term returns and "
            "volatility. A common heuristic sets equity exposure near 100 minus "
            "age, then adjusts for risk tolerance and horizon. Longer horizons "
            "and higher risk tolerance justify more equity; shorter horizons and "
            "low tolerance justify more fixed income and cash."
        ),
    },
    {
        "id": "kb-sip",
        "title": "Systematic investment plans (SIP) and rupee-cost averaging",
        "content": (
            "Systematic Investment Plans invest a fixed amount at regular "
            "intervals, smoothing entry price through rupee-cost averaging and "
            "enforcing disciplined saving. SIP amounts should be sized from "
            "monthly surplus after expenses and emergency-fund contributions, "
            "and split across asset classes per the target allocation."
        ),
    },
    {
        "id": "kb-diversification",
        "title": "Diversification and concentration risk",
        "content": (
            "Diversification across asset classes, sectors and geographies lowers "
            "idiosyncratic risk. A single holding above roughly 10 percent of the "
            "portfolio, or a single asset class above its strategic target, "
            "signals concentration risk that should be rebalanced over time."
        ),
    },
    {
        "id": "kb-risk-profile",
        "title": "Risk profiling",
        "content": (
            "Risk capacity (ability to take risk, driven by horizon, income "
            "stability and net worth) must be distinguished from risk tolerance "
            "(willingness). The binding constraint is the lower of the two. Short "
            "goals under three years should avoid volatile assets regardless of "
            "stated tolerance."
        ),
    },
    {
        "id": "kb-rebalancing",
        "title": "Rebalancing discipline",
        "content": (
            "Rebalancing restores the target allocation after market drift, "
            "typically on a calendar (annual) or threshold (5 percent band) "
            "basis. It mechanically sells high and buys low and controls risk "
            "creep from an appreciating equity sleeve."
        ),
    },
    {
        "id": "kb-tax-efficiency",
        "title": "Tax-efficient investing",
        "content": (
            "Use tax-advantaged accounts and long-term holding periods to reduce "
            "drag. Prefer low-cost index funds and ETFs for core exposure; keep "
            "turnover low. Locate tax-inefficient assets in sheltered accounts "
            "where available."
        ),
    },
]


class RagKnowledgeRepository(IKnowledgeRepository):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._docs = self._load_corpus(settings.rag_knowledge_path)
        self._doc_tokens = [Counter(_tokenize(d["content"] + " " + d["title"])) for d in self._docs]
        self._idf = self._compute_idf(self._doc_tokens)

    @staticmethod
    def _load_corpus(path: str | None) -> list[dict[str, str]]:
        if path:
            try:
                raw = json.loads(Path(path).read_text(encoding="utf-8"))
                if isinstance(raw, list) and raw:
                    return raw
                logger.warning("Knowledge file empty/invalid; using built-in corpus")
            except Exception:  # noqa: BLE001
                logger.warning("Failed to read knowledge file; using built-in corpus")
        return _DEFAULT_CORPUS

    @staticmethod
    def _compute_idf(doc_tokens: list[Counter]) -> dict[str, float]:
        n = len(doc_tokens) or 1
        df: Counter[str] = Counter()
        for tokens in doc_tokens:
            df.update(set(tokens))
        return {term: math.log((1 + n) / (1 + freq)) + 1.0 for term, freq in df.items()}

    def _vectorize(self, tokens: Counter) -> dict[str, float]:
        return {t: freq * self._idf.get(t, 1.0) for t, freq in tokens.items()}

    def _score(self, query_vec: dict[str, float], doc_vec: dict[str, float]) -> float:
        if not query_vec or not doc_vec:
            return 0.0
        common = set(query_vec) & set(doc_vec)
        dot = sum(query_vec[t] * doc_vec[t] for t in common)
        qn = math.sqrt(sum(v * v for v in query_vec.values()))
        dn = math.sqrt(sum(v * v for v in doc_vec.values()))
        return dot / (qn * dn) if qn and dn else 0.0

    def _retrieve_sync(self, query: str, top_k: int) -> list[KnowledgeSnippet]:
        query_vec = self._vectorize(Counter(_tokenize(query)))
        scored: list[tuple[float, dict[str, str]]] = []
        for doc, tokens in zip(self._docs, self._doc_tokens):
            score = self._score(query_vec, self._vectorize(tokens))
            scored.append((score, doc))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        results: list[KnowledgeSnippet] = []
        for score, doc in scored[:top_k]:
            if score <= 0:
                continue
            results.append(
                KnowledgeSnippet(
                    id=doc["id"],
                    title=doc["title"],
                    content=doc["content"],
                    score=round(score, 4),
                    source=doc.get("source", "internal-kb"),
                )
            )
        # Guarantee at least one snippet for downstream prompting.
        if not results and self._docs:
            doc = self._docs[0]
            results.append(
                KnowledgeSnippet(
                    id=doc["id"], title=doc["title"], content=doc["content"], score=0.0
                )
            )
        return results

    async def retrieve(self, query: str, *, top_k: int) -> list[KnowledgeSnippet]:
        return await asyncio.to_thread(self._retrieve_sync, query, top_k)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())
