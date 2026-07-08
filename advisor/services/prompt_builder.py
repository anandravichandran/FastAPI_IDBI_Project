"""Builds the DeepSeek prompt from deterministic analysis + retrieved context.

Keeping prompt construction isolated (Single Responsibility) makes it easy to
tune wording, inject retrieved knowledge, and unit-test the exact payload sent
to the model.
"""
from __future__ import annotations

import json

from advisor.domain.entities import KnowledgeSnippet, MarketSnapshot
from advisor.domain.interfaces.llm import LLMMessage
from advisor.schemas.request import AdviceRequest
from advisor.schemas.response import (
    AssetAllocation,
    DiversificationAdvice,
    EmergencyFundRecommendation,
    PortfolioAnalysis,
    RiskScore,
    SIPRecommendation,
)

_SYSTEM_PROMPT = (
    "You are a CFA-charterholder investment advisor. You explain a quantitative "
    "financial plan that has ALREADY been computed. Do not invent or change any "
    "numbers; only explain, justify, and add qualitative nuance. Be precise, "
    "neutral, and jargon-light. Always note that this is educational information, "
    "not personalized financial advice. Respond ONLY with a JSON object matching "
    "the requested schema."
)

_RESPONSE_SCHEMA_HINT = {
    "explanation": "string: 150-250 word plain-language rationale for the plan",
    "diversification_recommendations": ["string", "..."],
    "key_risks": ["string", "..."],
}


class PromptBuilder:
    def build_query(self, request: AdviceRequest) -> str:
        """Natural-language query used to retrieve RAG knowledge."""
        goals = ", ".join(g.name for g in request.goals) or "general wealth building"
        return (
            f"{request.risk_profile.tolerance.value} investor, "
            f"{request.risk_profile.investment_horizon_years}-year horizon, "
            f"goals: {goals}. Asset allocation, SIP sizing, emergency fund, "
            "diversification and rebalancing best practices."
        )

    def build_messages(
        self,
        *,
        request: AdviceRequest,
        risk: RiskScore,
        analysis: PortfolioAnalysis,
        allocation: AssetAllocation,
        sip: SIPRecommendation,
        emergency: EmergencyFundRecommendation,
        diversification: DiversificationAdvice,
        market: MarketSnapshot,
        knowledge: list[KnowledgeSnippet],
    ) -> list[LLMMessage]:
        context = {
            "investor": {
                "age": request.user_profile.age,
                "dependents": request.user_profile.dependents,
                "currency": request.user_profile.currency,
                "risk_tolerance": request.risk_profile.tolerance.value,
                "horizon_years": request.risk_profile.investment_horizon_years,
                "monthly_income": request.monthly_income,
                "monthly_expenses": request.monthly_expenses,
                "monthly_surplus": request.monthly_surplus,
                "current_savings": request.current_savings,
                "goals": [
                    {"name": g.name, "target_amount": g.target_amount,
                     "priority": g.priority.value}
                    for g in request.goals
                ],
            },
            "computed_plan": {
                "risk_score": risk.model_dump(mode="json"),
                "portfolio_analysis": analysis.model_dump(mode="json"),
                "target_allocation": allocation.model_dump(mode="json"),
                "sip": sip.model_dump(mode="json"),
                "emergency_fund": emergency.model_dump(mode="json"),
                "diversification": diversification.model_dump(mode="json"),
            },
            "market_snapshot": {
                "source": market.source,
                "degraded": market.degraded,
                "quotes": [
                    {"symbol": q.symbol, "price": q.price,
                     "change_percent_1d": q.change_percent_1d}
                    for q in market.quotes
                ],
            },
            "retrieved_knowledge": [
                {"title": k.title, "content": k.content} for k in knowledge
            ],
            "response_schema": _RESPONSE_SCHEMA_HINT,
        }

        user_prompt = (
            "Using ONLY the computed plan and retrieved knowledge below, produce the "
            "JSON response. Ground your reasoning in the retrieved knowledge and the "
            "investor's situation. Do not alter any numbers.\n\n"
            + json.dumps(context, indent=2, default=str)
        )
        return [
            LLMMessage(role="system", content=_SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_prompt),
        ]
