"""Pydantic transport models."""
from app.schemas.request import (
    AdviceRequest,
    Goal,
    PortfolioHolding,
    RiskProfile,
    UserProfile,
)
from app.schemas.response import (
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
