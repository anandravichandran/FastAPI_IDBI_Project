"""RAG knowledge repository for financial coaching.

Implements :class:`IKnowledgeRepository` with a dependency-light retrieval
engine over a curated corpus of personal-finance coaching principles.
Retrieval uses TF-IDF + cosine similarity so it works fully offline; the same
interface can later be backed by a vector database without touching callers.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
from collections import Counter
from pathlib import Path

from coach.core.config import Settings
from coach.core.logging import get_logger
from coach.domain.entities import KnowledgeSnippet
from coach.domain.interfaces.knowledge import IKnowledgeRepository

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_DEFAULT_CORPUS: list[dict[str, str]] = [
    {
        "id": "kb-50-30-20",
        "title": "The 50/30/20 budgeting rule",
        "content": (
            "A common budgeting guideline allocates roughly 50 percent of take-home "
            "pay to needs (housing, utilities, groceries, transport, minimum debt), "
            "30 percent to wants (dining, entertainment, shopping), and 20 percent to "
            "savings and investments. Persistent spending above these bands in the "
            "wants category is the clearest sign of overspending."
        ),
    },
    {
        "id": "kb-emergency-fund",
        "title": "Emergency fund sizing",
        "content": (
            "An emergency fund should cover three to six months of essential expenses, "
            "and six to twelve months for single-income households or variable pay. "
            "Hold it in liquid, capital-stable instruments. Do not take on new EMIs or "
            "increase investments aggressively until the emergency fund is in place."
        ),
    },
    {
        "id": "kb-foir",
        "title": "EMI affordability and FOIR",
        "content": (
            "Lenders assess the Fixed Obligation to Income Ratio (FOIR): the share of "
            "monthly income committed to all EMIs. Total EMIs should stay under about "
            "40 percent of net monthly income; for home loans many advisors prefer the "
            "housing EMI alone to stay under 30 to 35 percent. A new loan is affordable "
            "only if the resulting FOIR stays within these limits and the emergency fund "
            "is intact."
        ),
    },
    {
        "id": "kb-car-buying",
        "title": "Buying a car responsibly",
        "content": (
            "A widely used heuristic is the 20/4/10 rule: put at least 20 percent down, "
            "finance for no more than 4 years, and keep total transport costs (EMI, fuel, "
            "insurance, maintenance) under 10 percent of gross income. A car is a "
            "depreciating asset, so avoid stretching the budget or raiding long-term "
            "goals to buy one."
        ),
    },
    {
        "id": "kb-sip",
        "title": "Systematic Investment Plans (SIP)",
        "content": (
            "SIPs invest a fixed amount at regular intervals, smoothing entry price via "
            "rupee-cost averaging and enforcing discipline. Increase SIP contributions "
            "only from genuine, sustainable monthly surplus after essential expenses, "
            "EMIs and emergency-fund top-ups. Step-up SIPs that rise with income growth "
            "are an effective way to scale investing over time."
        ),
    },
    {
        "id": "kb-savings-rate",
        "title": "Improving your savings rate",
        "content": (
            "The savings rate is monthly surplus divided by income. Improve it by "
            "automating transfers on payday (pay yourself first), capping discretionary "
            "categories, renegotiating recurring bills and subscriptions, and directing "
            "windfalls and raises to investments before lifestyle inflation absorbs them. "
            "A rate of 20 percent or more is considered healthy."
        ),
    },
    {
        "id": "kb-overspending",
        "title": "Detecting and fixing overspending",
        "content": (
            "Overspending shows up as categories persistently exceeding their budget, a "
            "falling savings rate, or reliance on credit for routine expenses. Fix it by "
            "reviewing the largest discretionary categories first, setting category "
            "limits, and using a 24-hour rule for non-essential purchases."
        ),
    },
    {
        "id": "kb-goal-planning",
        "title": "Goal-based planning",
        "content": (
            "Assign every goal a target amount, date and monthly contribution. Short-term "
            "goals (under three years) belong in low-risk instruments; long-term goals "
            "can hold more equity. Fund high-priority and near-term goals first, and "
            "review progress quarterly."
        ),
    },
]


class RagKnowledgeRepository(IKnowledgeRepository):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._docs = self._load_corpus(settings.rag_knowledge_path)
        self._doc_tokens = [
            Counter(_tokenize(d["content"] + " " + d["title"])) for d in self._docs
        ]
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
            scored.append((self._score(query_vec, self._vectorize(tokens)), doc))
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
                    source=doc.get("source", "coaching-kb"),
                )
            )
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
