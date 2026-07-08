"""Investment-advisor API endpoints (v1)."""
from __future__ import annotations

from fastapi import APIRouter, status

from advisor.api.deps import AdvisorServiceDep
from advisor.schemas.request import AdviceRequest
from advisor.schemas.response import AdviceResponse

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.post(
    "/advice",
    response_model=AdviceResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a full investment-advice report",
    response_description="Portfolio analysis, risk score, allocation, SIP, "
    "emergency fund, diversification advice and a narrative explanation.",
)
async def create_advice(
    payload: AdviceRequest,
    service: AdvisorServiceDep,
) -> AdviceResponse:
    """Produce a personalized investment plan.

    The service combines deterministic financial-planning math with OpenBB
    market data, RAG-retrieved knowledge, and a DeepSeek V3 narrative.
    """
    return await service.advise(payload)
