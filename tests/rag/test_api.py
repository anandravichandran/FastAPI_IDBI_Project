"""API smoke tests for the RAG service.

Requires FastAPI's TestClient; skipped automatically when FastAPI/httpx are not
installed (e.g. in an air-gapped verification sandbox). Forces the light
backends via environment so no heavy dependency or real PDF is needed.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from rag.core.config import Settings  # noqa: E402
from rag.main import create_app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    os.environ["EMBEDDING_BACKEND"] = "hashing"
    os.environ["VECTOR_BACKEND"] = "memory"
    settings = Settings(embedding_backend="hashing", vector_backend="memory")
    return TestClient(create_app(settings))


def test_health(client: TestClient) -> None:
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_upload_text_as_pdf_is_rejected(client: TestClient) -> None:
    # The PDF parser rejects non-PDF filenames with 415.
    res = client.post(
        "/api/v1/documents",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 415


def test_query_without_documents_returns_empty(client: TestClient) -> None:
    res = client.post("/api/v1/rag/query", json={"query": "emergency fund"})
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 0
    assert body["messages"] is not None  # context still assembled
