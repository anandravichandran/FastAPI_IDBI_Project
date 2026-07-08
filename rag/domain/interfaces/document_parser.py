"""Port: document text extraction."""
from __future__ import annotations

from abc import ABC, abstractmethod

from rag.domain.entities import ParsedDocument


class IDocumentParser(ABC):
    """Extracts plain text from an uploaded document.

    Shipped with a PDF adapter (pypdf); swap or extend for DOCX/HTML without
    touching the service layer. Implementations are synchronous and CPU-bound;
    the API layer offloads them to a worker thread.
    """

    @abstractmethod
    def parse(self, *, document_id: str, filename: str, data: bytes) -> ParsedDocument:
        """Return the extracted text for an uploaded file.

        Raises:
            UnsupportedFileTypeError: if the file type is not supported.
            DocumentProcessingError: if the file cannot be read/parsed.
        """
        raise NotImplementedError
