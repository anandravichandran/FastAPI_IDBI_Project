"""Deterministic, boundary-aware text chunker.

Pure, dependency-free logic (no I/O, no framework, no randomness) so it is fully
unit-testable and reproducible. Produces overlapping character windows that
prefer to end on a natural boundary (paragraph → sentence → word) to avoid
cutting sentences mid-way, which improves downstream retrieval quality.
"""
from __future__ import annotations

import re

from rag.core.exceptions import DomainValidationError
from rag.domain.entities import DocumentChunk

_WS_RE = re.compile(r"[ \t\x0b\x0c\r]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")
# Sentence terminators followed by whitespace.
_SENTENCE_END_RE = re.compile(r"[.!?]\s")


class TextChunker:
    def __init__(
        self,
        *,
        chunk_size: int = 900,
        chunk_overlap: int = 150,
        min_chunk_chars: int = 60,
    ) -> None:
        if chunk_overlap >= chunk_size:
            raise DomainValidationError(
                "chunk_overlap must be smaller than chunk_size",
                details={"chunk_size": chunk_size, "chunk_overlap": chunk_overlap},
            )
        self._chunk_size = chunk_size
        self._overlap = chunk_overlap
        self._min_chars = min_chunk_chars

    def normalize(self, text: str) -> str:
        """Collapse runs of spaces/tabs and excessive blank lines."""
        text = (text or "").replace("\x00", " ")
        text = _WS_RE.sub(" ", text)
        text = _MULTI_NL_RE.sub("\n\n", text)
        # Trim trailing spaces on each line.
        text = "\n".join(line.strip() for line in text.split("\n"))
        return text.strip()

    def split(self, *, document_id: str, filename: str, text: str) -> list[DocumentChunk]:
        """Split ``text`` into ordered, overlapping :class:`DocumentChunk`s."""
        normalized = self.normalize(text)
        if not normalized:
            return []

        windows = self._windows(normalized)
        chunks: list[DocumentChunk] = []
        for ordinal, (start, end) in enumerate(windows):
            body = normalized[start:end].strip()
            if not body:
                continue
            if len(body) < self._min_chars and chunks:
                # Fold a tiny trailing remainder into the previous chunk.
                prev = chunks[-1]
                merged = f"{prev.text}\n{body}".strip()
                chunks[-1] = DocumentChunk(
                    chunk_id=prev.chunk_id,
                    document_id=document_id,
                    filename=filename,
                    ordinal=prev.ordinal,
                    text=merged,
                    start_char=prev.start_char,
                    end_char=end,
                    metadata={"merged": True},
                )
                continue
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{document_id}:{ordinal}",
                    document_id=document_id,
                    filename=filename,
                    ordinal=ordinal,
                    text=body,
                    start_char=start,
                    end_char=end,
                    metadata={},
                )
            )
        # Re-number ordinals to stay contiguous after any merges.
        renumbered: list[DocumentChunk] = []
        for i, c in enumerate(chunks):
            renumbered.append(
                DocumentChunk(
                    chunk_id=f"{document_id}:{i}",
                    document_id=c.document_id,
                    filename=c.filename,
                    ordinal=i,
                    text=c.text,
                    start_char=c.start_char,
                    end_char=c.end_char,
                    metadata=c.metadata,
                )
            )
        return renumbered

    # -- internals ---------------------------------------------------------
    def _windows(self, text: str) -> list[tuple[int, int]]:
        n = len(text)
        if n <= self._chunk_size:
            return [(0, n)]
        step = max(1, self._chunk_size - self._overlap)
        windows: list[tuple[int, int]] = []
        start = 0
        while start < n:
            hard_end = min(start + self._chunk_size, n)
            end = hard_end
            if hard_end < n:
                boundary = self._find_boundary(text, start, hard_end)
                if boundary > start + self._min_chars:
                    end = boundary
            windows.append((start, end))
            if end >= n:
                break
            nxt = end - self._overlap
            start = nxt if nxt > start else start + step
        return windows

    def _find_boundary(self, text: str, start: int, end: int) -> int:
        """Return the best split index in ``(start, end]`` preferring, in order:
        a paragraph break, a sentence end, then a word boundary."""
        window = text[start:end]
        para = window.rfind("\n\n")
        if para != -1 and para > 0:
            return start + para + 2
        # Last sentence terminator within the window.
        last = -1
        for m in _SENTENCE_END_RE.finditer(window):
            last = m.end()
        if last != -1:
            return start + last
        space = window.rfind(" ")
        if space != -1 and space > 0:
            return start + space + 1
        return end
