"""Retrieval & context-assembly endpoints.

``POST /rag/query``   → retrieve relevant chunks (optionally with context)
``POST /rag/context`` → grounded context + DeepSeek-ready ``messages`` payload
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from rag.api.deps import get_service
from rag.schemas.request import QueryRequest
from rag.schemas.response import ContextResponse, QueryResponse
from rag.services import RagService

router = APIRouter(prefix="/rag", tags=["retrieval"])


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Retrieve relevant chunks for a query",
)
async def query(
    payload: QueryRequest, service: RagService = Depends(get_service)
) -> QueryResponse:
    result = await run_in_threadpool(
        service.retrieve,
        payload.query,
        top_k=payload.top_k,
        document_ids=payload.document_ids,
    )
    context = None
    if payload.include_context:
        context = await run_in_threadpool(
            service.build_context,
            payload.query,
            top_k=payload.top_k,
            document_ids=payload.document_ids,
        )
    return QueryResponse.from_domain(result, context)


@router.post(
    "/context",
    response_model=ContextResponse,
    summary="Assemble grounded context for DeepSeek",
)
async def context(
    payload: QueryRequest, service: RagService = Depends(get_service)
) -> ContextResponse:
    ctx = await run_in_threadpool(
        service.build_context,
        payload.query,
        top_k=payload.top_k,
        document_ids=payload.document_ids,
    )
    return ContextResponse.from_domain(ctx)
