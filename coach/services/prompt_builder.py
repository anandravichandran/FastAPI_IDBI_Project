"""Builds the DeepSeek prompt for grounded, avatar-friendly coaching.

The prompt hard-constrains the model: it must ground its explanation in the
deterministic assessment and retrieved knowledge, must not invent numbers, and
must return strict JSON that maps onto the avatar response.
"""
from __future__ import annotations

import json
from collections.abc import Sequence

from coach.domain.entities import (
    ConversationTurn,
    CustomerFinancialProfile,
    FinancialSnapshot,
    KnowledgeSnippet,
    LLMMessage,
)
from coach.domain.enums import CoachIntent
from coach.services.affordability import Assessment

_SYSTEM = (
    "You are an enterprise financial coaching assistant speaking through a "
    "friendly mobile avatar. You explain money decisions in plain, warm, "
    "encouraging language for a general audience.\n"
    "STRICT RULES:\n"
    "1. Ground every statement in the CONTEXT provided. Never invent or alter "
    "numbers, verdicts, or figures — they are computed by a deterministic engine.\n"
    "2. Keep 'reply' to one short sentence suitable for a chat bubble / speech.\n"
    "3. 'detail' may be 2-4 short sentences. Avoid jargon; expand acronyms once.\n"
    "4. Be supportive and non-judgmental. This is educational, not regulated advice.\n"
    "5. Respond ONLY with a JSON object matching the requested schema. No markdown."
)

_SCHEMA_HINT = {
    "reply": "string, one short sentence",
    "detail": "string, 2-4 sentences",
    "avatar_speech": "string, <= 20 words, what the avatar says aloud",
    "emotion": "one of: happy, encouraging, neutral, concerned, celebrating",
    "action_items": ["short imperative string", "..."],
    "quick_replies": ["short follow-up question the user might tap", "..."],
}


class PromptBuilder:
    def build(
        self,
        *,
        message: str,
        intent: CoachIntent,
        profile: CustomerFinancialProfile,
        snapshot: FinancialSnapshot,
        assessment: Assessment,
        knowledge: Sequence[KnowledgeSnippet],
        history: Sequence[ConversationTurn],
    ) -> list[LLMMessage]:
        context = {
            "customer": {
                "name": profile.display_name,
                "currency": profile.currency,
            },
            "intent": intent.value,
            "financial_snapshot": {
                "monthly_income": snapshot.monthly_income,
                "monthly_expenses": snapshot.monthly_expenses,
                "monthly_surplus": snapshot.monthly_surplus,
                "savings_rate_pct": snapshot.savings_rate_pct,
                "total_savings": snapshot.total_savings,
                "total_monthly_sip": snapshot.total_sip,
                "emergency_fund_months": snapshot.emergency_fund_months,
                "total_monthly_emi": snapshot.total_monthly_emi,
                "foir_pct": snapshot.foir_pct,
                "top_categories": [
                    {"category": c.category.value, "amount": c.amount, "share_pct": c.share_pct}
                    for c in snapshot.top_categories
                ],
            },
            "deterministic_assessment": {
                "verdict": assessment.verdict.value,
                "headline": assessment.headline,
                "reasons": assessment.reasons,
                "metrics": assessment.metrics,
                "recommended_actions": assessment.actions,
            },
            "retrieved_knowledge": [
                {"title": k.title, "content": k.content} for k in knowledge
            ],
            "response_schema": _SCHEMA_HINT,
        }

        messages: list[LLMMessage] = [LLMMessage(role="system", content=_SYSTEM)]
        # Prior turns give the model short-term memory.
        for turn in history:
            role = "assistant" if turn.role == "coach" else "user"
            messages.append(LLMMessage(role=role, content=turn.content))
        messages.append(
            LLMMessage(
                role="user",
                content=(
                    f"Customer question: {message}\n\n"
                    f"CONTEXT (authoritative, do not contradict):\n"
                    f"{json.dumps(context, ensure_ascii=False)}\n\n"
                    "Return ONLY the JSON object described by response_schema."
                ),
            )
        )
        return messages
