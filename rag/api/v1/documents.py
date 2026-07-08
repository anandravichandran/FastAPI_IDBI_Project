"""Document ingestion & catalog endpoints.

CPU/IO-bound work (PDF parsing, embedding, vector writes) runs in a worker
thread via ``run_in_threadpool`` so the event loop stays responsive.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from rag.api.deps import get_service
from rag.core.exceptions import DomainValidationError
from rag.schemas.response import (
    DeleteResponse,
    DocumentListResponse,
    DocumentOut,
    IngestResponse,
    StatsResponse,
)
from rag.services import RagService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and index a PDF",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to ingest."),
    service: RagService = Depends(get_service),
) -> IngestResponse:
    data = await file.read()
    document = await run_in_threadpool(
        service.ingest_pdf, filename=file.filename or "upload.pdf", data=data
    )
    return IngestResponse.from_domain(document)


@router.get("", response_model=DocumentListResponse, summary="List indexed documents")
async def list_documents(
    service: RagService = Depends(get_service),
) -> DocumentListResponse:
    docs = await run_in_threadpool(service.list_documents)
    return DocumentListResponse.from_domain(docs)


@router.get("/stats", response_model=StatsResponse, summary="Index statistics")
async def stats(service: RagService = Depends(get_service)) -> StatsResponse:
    data = await run_in_threadpool(service.stats)
    return StatsResponse(**data)


@router.get(
    "/{document_id}", response_model=DocumentOut, summary="Get a document record"
)
async def get_document(
    document_id: str, service: RagService = Depends(get_service)
) -> DocumentOut:
    if not document_id.strip():
        raise DomainValidationError("document_id is required.")
    doc = await run_in_threadpool(service.get_document, document_id)
    return DocumentOut.from_domain(doc)


@router.delete(
    "/{document_id}", response_model=DeleteResponse, summary="Delete a document"
)
async def delete_document(
    document_id: str, service: RagService = Depends(get_service)
) -> DeleteResponse:
    removed = await run_in_threadpool(service.delete_document, document_id)
    return DeleteResponse(document_id=document_id, chunks_removed=removed)
