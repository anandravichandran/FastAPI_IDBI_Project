"""Coach orchestration — the single use-case entrypoint for the API layer.

Flow for a chat turn:
  1. Load the customer's financial profile (transactions, budget, savings, goals).
  2. Compute a deterministic :class:`FinancialSnapshot`.
  3. Classify intent and run the matching deterministic assessment.
  4. Retrieve relevant knowledge via RAG (concurrently with nothing blocking).
  5. Ask DeepSeek V3 to narrate the assessment as avatar-friendly JSON.
  6. Persist the turn and return a structured response.

The service depends only on domain ports (Dependency Inversion) and degrades
gracefully: if DeepSeek is unavailable it returns a deterministic narration.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Sequence

from coach.core.config import Settings
from coach.core.logging import get_logger
from coach.domain.entities import (
    ConversationTurn,
    CustomerFinancialProfile,
    FinancialSnapshot,
    KnowledgeSnippet,
    LLMMessage,
)
from coach.domain.enums import AvatarEmotion, CoachIntent, MessageRole, Verdict
from coach.domain.interfaces import (
    IConversationRepository,
    ICustomerRepository,
    IKnowledgeRepository,
    ILLMClient,
)
from coach.services.affordability import AffordabilityEngine, Assessment
from coach.services.financial_analyzer import FinancialAnalyzer
from coach.services.intent_classifier import IntentClassifier
from coach.services.prompt_builder import PromptBuilder

logger = get_logger(__name__)

_DISCLAIMER = (
    "This is educational information generated from your own financial data, "
    "not personalized investment advice. Consult a licensed advisor for decisions."
)

_EMOTION_BY_VERDICT = {
    Verdict.YES: AvatarEmotion.HAPPY,
    Verdict.CAUTION: AvatarEmotion.CONCERNED,
    Verdict.NO: AvatarEmotion.CONCERNED,
    Verdict.INFO: AvatarEmotion.ENCOURAGING,
}
_ANIMATION_BY_VERDICT = {
    Verdict.YES: "thumbs_up",
    Verdict.CAUTION: "think",
    Verdict.NO: "shake_head",
    Verdict.INFO: "nod",
}


class CoachResult:
    """Plain container returned to the API layer (mapped to Pydantic there)."""

    def __init__(
        self,
        *,
        session_id: str,
        message_id: str,
        customer_id: str,
        intent: CoachIntent,
        assessment: Assessment,
        confidence: float,
        reply: str,
        detail: str,
        avatar_speech: str,
        emotion: AvatarEmotion,
        action_items: list[str],
        quick_replies: list[str],
        knowledge: Sequence[KnowledgeSnippet],
        llm_used: bool,
        llm_model: str,
        generated_at: dt.datetime,
    ) -> None:
        self.session_id = session_id
        self.message_id = message_id
        self.customer_id = customer_id
        self.intent = intent
        self.assessment = assessment
        self.confidence = confidence
        self.reply = reply
        self.detail = detail
        self.avatar_speech = avatar_speech
        self.emotion = emotion
        self.action_items = action_items
        self.quick_replies = quick_replies
        self.knowledge = list(knowledge)
        self.llm_used = llm_used
        self.llm_model = llm_model
        self.generated_at = generated_at
        self.disclaimers = [_DISCLAIMER]


class CoachService:
    def __init__(
        self,
        *,
        settings: Settings,
        customers: ICustomerRepository,
        knowledge: IKnowledgeRepository,
        conversations: IConversationRepository,
        llm: ILLMClient,
        analyzer: FinancialAnalyzer,
        affordability: AffordabilityEngine,
        intent_classifier: IntentClassifier,
        prompt_builder: PromptBuilder,
    ) -> None:
        self._s = settings
        self._customers = customers
        self._knowledge = knowledge
        self._conversations = conversations
        self._llm = llm
        self._analyzer = analyzer
        self._affordability = affordability
        self._intents = intent_classifier
        self._prompts = prompt_builder

    # -- public use cases ----------------------------------------------------
    async def chat(
        self, *, customer_id: str, message: str, session_id: str | None
    ) -> CoachResult:
        now = dt.datetime.now(dt.timezone.utc)
        session_id = session_id or f"sess-{uuid.uuid4().hex[:12]}"
        profile = await self._customers.get_profile(customer_id)
        snapshot = self._analyzer.build_snapshot(profile)

        intent, confidence = self._intents.classify(message)
        amount = self._intents.extract_amount(message)
        assessment = self._run_assessment(intent, snapshot, profile, amount)

        knowledge = await self._knowledge.retrieve(
            self._knowledge_query(intent, message), top_k=self._s.rag_top_k
        )
        history = await self._conversations.history(
            customer_id=customer_id,
            session_id=session_id,
            limit=self._s.history_context_turns,
        )

        narration, llm_used, llm_model = await self._narrate(
            message=message,
            intent=intent,
            profile=profile,
            snapshot=snapshot,
            assessment=assessment,
            knowledge=knowledge,
            history=history,
        )

        result = CoachResult(
            session_id=session_id,
            message_id=f"msg-{uuid.uuid4().hex[:12]}",
            customer_id=customer_id,
            intent=intent,
            assessment=assessment,
            confidence=confidence,
            reply=narration["reply"],
            detail=narration["detail"],
            avatar_speech=narration["avatar_speech"],
            emotion=narration["emotion"],
            action_items=narration["action_items"],
            quick_replies=narration["quick_replies"],
            knowledge=knowledge,
            llm_used=llm_used,
            llm_model=llm_model,
            generated_at=now,
        )

        # Persist both sides of the exchange.
        await self._conversations.append(
            ConversationTurn(
                session_id=session_id, customer_id=customer_id,
                role=MessageRole.USER.value, content=message,
                created_at=now, intent=intent.value,
            )
        )
        await self._conversations.append(
            ConversationTurn(
                session_id=session_id, customer_id=customer_id,
                role=MessageRole.COACH.value, content=result.reply,
                created_at=now, intent=intent.value,
            )
        )
        return result

    async def history(
        self, *, customer_id: str, session_id: str | None, limit: int | None
    ) -> list[ConversationTurn]:
        # Ensure the customer exists (raises CustomerNotFoundError otherwise).
        await self._customers.get_profile(customer_id)
        return await self._conversations.history(
            customer_id=customer_id, session_id=session_id, limit=limit
        )

    async def summary(self, *, customer_id: str) -> tuple[CustomerFinancialProfile, FinancialSnapshot]:
        profile = await self._customers.get_profile(customer_id)
        snapshot = self._analyzer.build_snapshot(profile)
        return profile, snapshot

    def health_score(self, snapshot: FinancialSnapshot) -> tuple[int, str]:
        """Public accessor for the deterministic financial-health score.

        Exposes the stateless analyzer computation through the service's public
        API so callers (e.g. the /coach/summary endpoint) never reach into the
        service's private ``_analyzer`` attribute (encapsulation / Law of
        Demeter). Behaviour is identical to the previous inlined call.
        """
        return self._analyzer.health_score(snapshot)

    # -- internals -----------------------------------------------------------
    def _run_assessment(
        self,
        intent: CoachIntent,
        snapshot: FinancialSnapshot,
        profile: CustomerFinancialProfile,
        amount: float | None,
    ) -> Assessment:
        engine = self._affordability
        if intent == CoachIntent.BUY_CAR:
            return engine.assess_car(snapshot, profile, amount)
        if intent == CoachIntent.HOME_LOAN:
            return engine.assess_home_loan(snapshot, profile, amount)
        if intent == CoachIntent.INCREASE_SIP:
            return engine.assess_increase_sip(snapshot, amount)
        if intent == CoachIntent.OVERSPENDING:
            return engine.assess_overspending(snapshot)
        if intent == CoachIntent.IMPROVE_SAVINGS:
            return engine.assess_improve_savings(snapshot)
        return engine.assess_overspending(snapshot)  # sensible default for general Q&A

    @staticmethod
    def _knowledge_query(intent: CoachIntent, message: str) -> str:
        topic = {
            CoachIntent.BUY_CAR: "buying a car affordability EMI down payment",
            CoachIntent.HOME_LOAN: "home loan affordability FOIR EMI eligibility",
            CoachIntent.INCREASE_SIP: "SIP systematic investment plan increase surplus",
            CoachIntent.OVERSPENDING: "overspending budgeting 50/30/20 discretionary",
            CoachIntent.IMPROVE_SAVINGS: "improve savings rate pay yourself first",
            CoachIntent.GENERAL: "personal finance budgeting savings",
        }[intent]
        return f"{topic}. {message}"

    async def _narrate(
        self, **kwargs
    ) -> tuple[dict, bool, str]:
        """Ask the LLM to narrate; fall back to a deterministic template."""
        assessment: Assessment = kwargs["assessment"]
        fallback = self._deterministic_narration(assessment)

        if not self._s.llm_enabled:
            return fallback, False, "deterministic-fallback"

        messages = self._prompts.build(**kwargs)
        try:
            result = await self._llm.complete(messages, json_mode=True)
            parsed = self._parse_llm_json(result.content, assessment)
            return parsed, True, result.model
        except Exception as exc:  # noqa: BLE001 - never fail the request on LLM issues
            logger.warning("LLM narration failed; using fallback", extra={"error": str(exc)})
            return fallback, False, "deterministic-fallback"

    def _parse_llm_json(self, content: str, assessment: Assessment) -> dict:
        try:
            data = json.loads(content)
        except (ValueError, TypeError):
            return self._deterministic_narration(assessment)
        emotion = self._coerce_emotion(data.get("emotion"), assessment.verdict)
        return {
            "reply": str(data.get("reply") or assessment.headline)[:300],
            "detail": str(data.get("detail") or " ".join(assessment.reasons))[:1200],
            "avatar_speech": str(data.get("avatar_speech") or assessment.headline)[:200],
            "emotion": emotion,
            "action_items": _as_str_list(data.get("action_items"), assessment.actions),
            "quick_replies": _as_str_list(
                data.get("quick_replies"), _default_quick_replies()
            ),
        }

    @staticmethod
    def _coerce_emotion(value: object, verdict: Verdict) -> AvatarEmotion:
        if isinstance(value, str):
            try:
                return AvatarEmotion(value.lower())
            except ValueError:
                pass
        return _EMOTION_BY_VERDICT.get(verdict, AvatarEmotion.NEUTRAL)

    def _deterministic_narration(self, assessment: Assessment) -> dict:
        detail = assessment.headline
        if assessment.reasons:
            detail = assessment.headline + " " + " ".join(assessment.reasons)
        return {
            "reply": assessment.headline,
            "detail": detail,
            "avatar_speech": assessment.headline,
            "emotion": _EMOTION_BY_VERDICT.get(assessment.verdict, AvatarEmotion.NEUTRAL),
            "action_items": list(assessment.actions),
            "quick_replies": _default_quick_replies(),
        }

    def animation_for(self, verdict: Verdict) -> str:
        return _ANIMATION_BY_VERDICT.get(verdict, "idle")


def _as_str_list(value: object, default: list[str]) -> list[str]:
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
        if items:
            return items[:5]
    return default[:5]


def _default_quick_replies() -> list[str]:
    return [
        "Am I overspending?",
        "How can I improve savings?",
        "Should I increase my SIP?",
    ]
