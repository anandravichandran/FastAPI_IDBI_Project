"""PDF text-extraction adapter (pypdf).

``pypdf`` is imported lazily so the package can be imported — and the pure
domain/service layers unit-tested — without the dependency installed. If a real
PDF is uploaded and pypdf is missing, a clear configuration error is raised.
"""
from __future__ import annotations

import io

from rag.core.exceptions import (
    ConfigurationError,
    DocumentProcessingError,
    UnsupportedFileTypeError,
)
from rag.core.logging import get_logger
from rag.domain.entities import ParsedDocument
from rag.domain.enums import FileType
from rag.domain.interfaces import IDocumentParser

logger = get_logger(__name__)


class PdfDocumentParser(IDocumentParser):
    """Extract text from PDF bytes using pypdf."""

    def __init__(self, *, max_pages: int | None = None) -> None:
        self._max_pages = max_pages

    def parse(self, *, document_id: str, filename: str, data: bytes) -> ParsedDocument:
        try:
            FileType.from_filename(filename)
        except ValueError as exc:
            raise UnsupportedFileTypeError(
                "Only PDF uploads are supported.",
                details={"filename": filename},
            ) from exc

        if not data:
            raise DocumentProcessingError("Uploaded file is empty.")

        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ConfigurationError(
                "pypdf is not installed; cannot parse PDF uploads. "
                "Install it with `pip install pypdf`."
            ) from exc

        try:
            reader = PdfReader(io.BytesIO(data))
            pages = reader.pages
            if self._max_pages is not None:
                pages = pages[: self._max_pages]
            parts: list[str] = []
            for page in pages:
                extracted = page.extract_text() or ""
                if extracted.strip():
                    parts.append(extracted)
            text = "\n\n".join(parts)
            page_count = len(reader.pages)
        except Exception as exc:  # noqa: BLE001 - surface as a domain error
            logger.warning("PDF parse failed", extra={"doc_filename": filename})
            raise DocumentProcessingError(
                "Could not read the PDF; it may be corrupt or password-protected.",
                details={"filename": filename},
            ) from exc

        if not text.strip():
            raise DocumentProcessingError(
                "No extractable text found in the PDF (it may be a scanned image; "
                "OCR is required).",
                details={"filename": filename},
            )

        return ParsedDocument(
            document_id=document_id,
            filename=filename,
            text=text,
            page_count=page_count,
        )
