"""Application configuration for the RAG service.

Everything is environment-driven via ``pydantic-settings`` so the same image
runs across local/dev/staging/production without code changes. Chunking sizes,
the embedding model, the vector-store backend and retrieval parameters are all
configuration — not magic numbers — so they can be tuned per deployment without
touching logic.

Two backends are pluggable behind the domain ports:

* ``embedding_backend``  — ``sentence_transformers`` (production) or ``hashing``
  (a dependency-light, deterministic fallback used for tests / air-gapped runs).
* ``vector_backend``     — ``chromadb`` (production) or ``memory`` (in-process
  cosine store used for tests / air-gapped runs).

In non-production environments the composition root will transparently fall
back to the light backends if the heavy libraries are not installed.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "RAG Service"
    app_version: str = "1.0.0"
    environment: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # --- Logging ---
    log_level: str = "INFO"
    log_json: bool = True

    # --- Uploads ---
    max_upload_mb: float = Field(default=25.0, gt=0, le=200)

    # --- Chunking (character-based, boundary-aware) ---
    chunk_size: int = Field(default=900, ge=100, le=8000)
    chunk_overlap: int = Field(default=150, ge=0, le=2000)
    min_chunk_chars: int = Field(default=60, ge=1)

    # --- Embeddings ---
    # "sentence_transformers" | "hashing"
    embedding_backend: str = "sentence_transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # Dimensionality used by the hashing fallback embedder.
    hashing_embedding_dim: int = Field(default=384, ge=32, le=4096)
    embedding_batch_size: int = Field(default=32, ge=1, le=512)

    # --- Vector store ---
    # "chromadb" | "memory"
    vector_backend: str = "chromadb"
    chroma_persist_dir: str = "./.chroma"
    chroma_collection: str = "documents"

    # --- Retrieval ---
    default_top_k: int = Field(default=5, ge=1, le=50)
    max_top_k: int = Field(default=20, ge=1, le=100)
    # Drop retrieved chunks scoring below this cosine similarity (0 disables).
    min_relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # --- Context assembly for DeepSeek ---
    max_context_chars: int = Field(default=6000, ge=500, le=60000)
    context_separator: str = "\n\n---\n\n"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}

    @property
    def allow_backend_fallback(self) -> bool:
        """Outside production, degrade gracefully to the light backends when the
        heavy libraries (sentence-transformers / chromadb) are unavailable."""
        return not self.is_production

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
