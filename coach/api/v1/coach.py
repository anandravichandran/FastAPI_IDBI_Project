"""Financial coach endpoints: /coach/chat, /coach/history, /coach/summary."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Query, status

from coach.api.deps import CoachServiceDep
from coach.domain.enums import Verdict
from coach.schemas.request import ChatRequest
from coach.schemas.response import (
    AvatarState,
    CategoryBreakdown,
    ChatResponse,
    GoalProgress,
    HistoryResponse,
    HistoryTurn,
    Insight,
    QuickReply,
    SourceRef,
    SummaryResponse,
)
from coach.services.coach_service import CoachResult

router = APIRouter(prefix="/coach", tags=["coach"])

_VERDICT_STATUS = {
    Verdict.YES: "good",
    Verdict.CAUTION: "warn",
    Verdict.NO: "bad",
    Verdict.INFO: "neutral",
}


def _to_chat_response(service, result: CoachResult) -> ChatResponse:
    a = result.assessment
    insights = [
        Insight(
            label=_pretty(key),
            value=_fmt(value),
            status=_VERDICT_STATUS.get(a.verdict, "neutral"),
        )
        for key, value in list(a.metrics.items())[:5]
    ]
    return ChatResponse(
        session_id=result.session_id,
        message_id=result.message_id,
        customer_id=result.customer_id,
        intent=result.intent,
        verdict=a.verdict,
        confidence=result.confidence,
        reply=result.reply,
        detail=result.detail,
        avatar=AvatarState(
            emotion=result.emotion,
            animation=service.animation_for(a.verdict),
            tone="cautious" if a.verdict in {Verdict.CAUTION, Verdict.NO} else "friendly",
            speech=result.avatar_speech,
        ),
        insights=insights,
        action_items=result.action_items,
        quick_replies=[QuickReply(label=q, payload=q) for q in result.quick_replies],
        llm_used=result.llm_used,
        llm_model=result.llm_model,
        sources=[
            SourceRef(id=k.id, title=k.title, source=k.source, score=k.score)
            for k in result.knowledge
        ],
        disclaimers=result.disclaimers,
        generated_at=result.generated_at,
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask the financial coach a question",
)
async def chat(payload: ChatRequest, service: CoachServiceDep) -> ChatResponse:
    """Answer a natural-language money question grounded in the customer's data.

    Handles intents such as \"Can I buy a car?\", \"Should I increase SIP?\",
    \"Can I afford a home loan?\", \"Am I overspending?\" and
    \"How can I improve savings?\". Returns an avatar-ready JSON payload.
    """
    result = await service.chat(
        customer_id=payload.customer_id,
        message=payload.message,
        session_id=payload.session_id,
    )
    return _to_chat_response(service, result)


@router.get(
    "/history",
    response_model=HistoryResponse,
    summary="Retrieve conversation history",
)
async def history(
    service: CoachServiceDep,
    customer_id: str = Query(..., min_length=1, examples=["cust-001"]),
    session_id: str | None = Query(default=None, examples=["sess-abc123"]),
    limit: int = Query(default=20, ge=1, le=200),
) -> HistoryResponse:
    """Return recent conversation turns for a customer (optionally one session)."""
    turns = await service.history(
        customer_id=customer_id, session_id=session_id, limit=limit
    )
    return HistoryResponse(
        customer_id=customer_id,
        session_id=session_id,
        count=len(turns),
        turns=[
            HistoryTurn(
                role=t.role, content=t.content, intent=t.intent, created_at=t.created_at
            )
            for t in turns
        ],
    )


@router.get(
    "/summary",
    response_model=SummaryResponse,
    summary="Financial health summary",
)
async def summary(
    service: CoachServiceDep,
    customer_id: str = Query(..., min_length=1, examples=["cust-001"]),
) -> SummaryResponse:
    """Return a deterministic financial-health summary for the avatar home screen."""
    profile, snap = await service.summary(customer_id=customer_id)
    score, grade = service._analyzer.health_score(snap)  # analyzer is stateless

    highlights: list[str] = []
    if snap.savings_rate_pct >= 20:
        highlights.append(f"Healthy savings rate of {snap.savings_rate_pct}%.")
    if snap.emergency_fund_months >= 6:
        highlights.append(f"Emergency fund covers {snap.emergency_fund_months} months.")
    if snap.overspending_categories:
        names = ", ".join(c.category.value for c in snap.overspending_categories)
        highlights.append(f"Over budget in: {names}.")

    recommendations: list[str] = []
    if snap.savings_rate_pct < 20:
        recommendations.append("Automate a payday transfer to lift your savings rate toward 20%.")
    if snap.emergency_fund_months < 6:
        recommendations.append("Top up the emergency fund toward 6 months of expenses.")
    if snap.foir_pct > 40:
        recommendations.append("Reduce EMI load; total EMIs exceed 40% of income.")
    if not recommendations:
        recommendations.append("You're on track — consider a step-up SIP to accelerate goals.")

    return SummaryResponse(
        customer_id=profile.customer_id,
        display_name=profile.display_name,
        currency=profile.currency,
        generated_at=dt.datetime.now(dt.timezone.utc),
        monthly_income=snap.monthly_income,
        monthly_expenses=snap.monthly_expenses,
        monthly_surplus=snap.monthly_surplus,
        savings_rate_pct=snap.savings_rate_pct,
        total_savings=snap.total_savings,
        emergency_fund_months=snap.emergency_fund_months,
        total_monthly_emi=snap.total_monthly_emi,
        foir_pct=snap.foir_pct,
        financial_health_score=score,
        health_grade=grade,
        top_categories=[
            CategoryBreakdown(
                category=c.category.value,
                amount=c.amount,
                share_pct=c.share_pct,
                budget_limit=c.budget_limit,
                over_budget=c.over_budget,
            )
            for c in snap.top_categories
        ],
        overspending=[
            CategoryBreakdown(
                category=c.category.value,
                amount=c.amount,
                share_pct=c.share_pct,
                budget_limit=c.budget_limit,
                over_budget=c.over_budget,
            )
            for c in snap.overspending_categories
        ],
        goals=[
            GoalProgress(
                name=g.name,
                target_amount=g.target_amount,
                saved_amount=g.saved_amount,
                progress_pct=g.progress_pct,
                priority=g.priority,
            )
            for g in profile.goals
        ],
        highlights=highlights,
        recommendations=recommendations,
        disclaimers=[
            "Educational information derived from your own financial data, "
            "not personalized investment advice."
        ],
    )


def _pretty(key: str) -> str:
    return key.replace("_", " ").replace("pct", "%").strip().capitalize()


def _fmt(value: float) -> str:
    if isinstance(value, float) and value.is_integer():
        return f"{int(value):,}"
    if isinstance(value, (int, float)):
        return f"{value:,.2f}" if abs(value) < 1000 else f"{value:,.0f}"
    return str(value)
