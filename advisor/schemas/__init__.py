"""Pydantic transport models."""
from advisor.schemas.request import (
    AdviceRequest,
    Goal,
    PortfolioHolding,
    RiskProfile,
    UserProfile,
)
from advisor.schemas.response import (
    AdviceResponse,
    AllocationItem,
    AssetAllocation,
    CurrentAllocationItem,
    DiversificationAdvice,
    EmergencyFundRecommendation,
    KnowledgeReference,
    PortfolioAnalysis,
    RiskScore,
    SIPRecommendation,
)

__all__ = [
    "AdviceRequest",
    "Goal",
    "PortfolioHolding",
    "RiskProfile",
    "UserProfile",
    "AdviceResponse",
    "AllocationItem",
    "AssetAllocation",
    "CurrentAllocationItem",
    "DiversificationAdvice",
    "EmergencyFundRecommendation",
    "KnowledgeReference",
    "PortfolioAnalysis",
    "RiskScore",
    "SIPRecommendation",
]
