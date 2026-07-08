"""Unit tests for the deterministic TextChunker."""
from __future__ import annotations

import pytest

from rag.core.exceptions import DomainValidationError
from rag.services import TextChunker


def test_short_text_single_chunk() -> None:
    chunker = TextChunker(chunk_size=200, chunk_overlap=40, min_chunk_chars=10)
    chunks = chunker.split(document_id="d1", filename="f.pdf", text="Hello world.")
    assert len(chunks) == 1
    assert chunks[0].ordinal == 0
    assert chunks[0].document_id == "d1"
    assert chunks[0].chunk_id == "d1:0"


def test_empty_text_no_chunks() -> None:
    chunker = TextChunker(chunk_size=200, chunk_overlap=40)
    assert chunker.split(document_id="d1", filename="f.pdf", text="   \n\n ") == []


def test_long_text_is_chunked_with_overlap() -> None:
    chunker = TextChunker(chunk_size=120, chunk_overlap=30, min_chunk_chars=20)
    text = " ".join(f"sentence number {i} about savings." for i in range(40))
    chunks = chunker.split(document_id="d1", filename="f.pdf", text=text)
    assert len(chunks) > 1
    # Ordinals are contiguous starting at zero.
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    # Chunks respect the configured size (allowing boundary slack).
    assert all(len(c.text) <= 120 for c in chunks)


def test_normalize_collapses_whitespace() -> None:
    chunker = TextChunker(chunk_size=200, chunk_overlap=20)
    assert chunker.normalize("a\t  b\n\n\n\nc  ") == "a b\n\nc"


def test_overlap_must_be_smaller_than_size() -> None:
    with pytest.raises(DomainValidationError):
        TextChunker(chunk_size=100, chunk_overlap=100)
