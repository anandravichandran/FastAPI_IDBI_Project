"""Lightweight, deterministic intent classification.

Maps a free-text question to a :class:`CoachIntent` using keyword scoring. This
keeps routing fast, cheap and testable; the LLM is reserved for explanation,
not control flow. A monetary-amount parser extracts figures like
\"12 lakh\", \"1.2cr\" or \"₹800000\" for affordability questions.
"""
from __future__ import annotations

import re

from coach.domain.enums import CoachIntent

_KEYWORDS: dict[CoachIntent, tuple[str, ...]] = {
    CoachIntent.BUY_CAR: ("car", "vehicle", "bike", "automobile", "scooter"),
    CoachIntent.HOME_LOAN: ("home loan", "house", "home", "mortgage", "property", "flat", "apartment"),
    CoachIntent.INCREASE_SIP: ("sip", "mutual fund", "invest more", "increase investment", "step up"),
    CoachIntent.OVERSPENDING: ("overspend", "spending too much", "spend too much", "budget", "expenses high", "am i spending"),
    CoachIntent.IMPROVE_SAVINGS: ("save more", "improve savings", "savings", "cut expenses", "reduce spending", "emergency fund"),
}

_AMOUNT_RE = re.compile(
    r"(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*\.?[0-9]*)\s*(lakh|lakhs|lac|lacs|crore|crores|cr|k|thousand|million|m)?",
    re.IGNORECASE,
)
_MULTIPLIERS = {
    "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5,
    "crore": 1e7, "crores": 1e7, "cr": 1e7,
    "k": 1e3, "thousand": 1e3,
    "million": 1e6, "m": 1e6,
}


class IntentClassifier:
    def classify(self, message: str) -> tuple[CoachIntent, float]:
        text = message.lower()
        scores: dict[CoachIntent, int] = {}
        for intent, words in _KEYWORDS.items():
            hits = sum(1 for w in words if w in text)
            if hits:
                scores[intent] = hits
        # Disambiguate: an explicit "loan"/"afford" with car -> BUY_CAR stays.
        if not scores:
            return CoachIntent.GENERAL, 0.4
        best = max(scores, key=lambda k: scores[k])
        # Confidence scales with keyword hits, capped.
        confidence = min(0.95, 0.55 + 0.15 * scores[best])
        return best, round(confidence, 2)

    def extract_amount(self, message: str) -> float | None:
        """Return the most likely target amount mentioned in the message."""
        candidates: list[float] = []
        for match in _AMOUNT_RE.finditer(message):
            raw, unit = match.group(1), (match.group(2) or "").lower()
            if not raw or raw in {"."}:
                continue
            try:
                value = float(raw.replace(",", ""))
            except ValueError:
                continue
            if unit:
                value *= _MULTIPLIERS.get(unit, 1.0)
            # Ignore tiny bare numbers that are likely not amounts (e.g. "2 cars").
            if value >= 1000:
                candidates.append(value)
        return max(candidates) if candidates else None
