"""Pydantic response models (transport/DTO layer)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from advisor.domain.enums import AssetClass, EmergencyFundStatus, RiskBand


class AllocationItem(BaseModel):
    asset_class: AssetClass
    target_pct: float = Field(..., ge=0, le=100)
    rationale: str | None = None


class CurrentAllocationItem(BaseModel):
    asset_class: AssetClass
    current_pct: float = Field(..., ge=0, le=100)
    current_value: float = Field(..., ge=0)


class PortfolioAnalysis(BaseModel):
    total_value: float = Field(..., ge=0)
    holdings_count: int = Field(..., ge=0)
    largest_position_pct: float = Field(..., ge=0, le=100)
    current_allocation: list[CurrentAllocationItem] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)


class RiskScore(BaseModel):
    score: float = Field(..., ge=0, le=100, description="0 = defensive, 100 = aggressive")
    band: RiskBand
    rationale: str


class AssetAllocation(BaseModel):
    target: list[AllocationItem]
    summary: str


class SIPRecommendation(BaseModel):
    recommended_monthly_amount: float = Field(..., ge=0)
    allocations: list[AllocationItem] = Field(default_factory=list)
    expected_annual_return_pct: float = Field(..., ge=0, le=100)
    notes: str


class EmergencyFundRecommendation(BaseModel):
    recommended_amount: float = Field(..., ge=0)
    months_of_expenses: float = Field(..., ge=0)
    current_coverage_months: float = Field(..., ge=0)
    shortfall: float = Field(..., ge=0)
    status: EmergencyFundStatus
    notes: str


class DiversificationAdvice(BaseModel):
    diversification_score: float = Field(..., ge=0, le=100)
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class KnowledgeReference(BaseModel):
    id: str
    title: str
    source: str
    score: float


class AdviceResponse(BaseModel):
    """Complete investment-advice payload returned to the client."""

    request_id: str | None = None
    generated_at: datetime
    llm_model: str
    llm_used: bool = Field(
        ..., description="True when DeepSeek generated the narrative explanation."
    )
    market_data_source: str
    portfolio_analysis: PortfolioAnalysis
    risk_score: RiskScore
    asset_allocation: AssetAllocation
    sip_recommendation: SIPRecommendation
    emergency_fund: EmergencyFundRecommendation
    diversification: DiversificationAdvice
    explanation: str
    sources: list[KnowledgeReference] = Field(default_factory=list)
    disclaimers: list[str] = Field(default_factory=list)
