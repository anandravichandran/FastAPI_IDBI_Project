"""Request DTOs for the RAG API.

PDF uploads arrive as multipart ``UploadFile`` (see the documents router), so
the only JSON request body is the retrieval/context query.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "query": "What is an emergency fund and how big should it be?",
                "top_k": 5,
                "include_context": True,
            }
        },
    )

    query: str = Field(
        ..., min_length=1, max_length=4000, description="Natural-language query."
    )
    top_k: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Max chunks to retrieve (defaults to the service setting).",
    )
    document_ids: list[str] | None = Field(
        default=None,
        description="Optional list of document ids to restrict the search to.",
    )
    include_context: bool = Field(
        default=True,
        description="When true, also assemble a DeepSeek-ready context payload.",
    )
