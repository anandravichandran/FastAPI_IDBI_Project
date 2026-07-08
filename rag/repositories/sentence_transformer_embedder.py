"""Sentence Transformers embedding adapter (production).

The ``sentence-transformers`` model is loaded lazily on first use so importing
this module is cheap and the package can be imported without the (heavy)
dependency present. Model inference is CPU/GPU-bound; the API layer offloads
calls to a worker thread.
"""
from __future__ import annotations

from collections.abc import Sequence
from threading import Lock

from rag.core.exceptions import ConfigurationError, EmbeddingError
from rag.core.logging import get_logger
from rag.domain.entities import Vector
from rag.domain.interfaces import IEmbedder

logger = get_logger(__name__)


class SentenceTransformerEmbedder(IEmbedder):
    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        *,
        batch_size: int = 32,
        normalize: bool = True,
    ) -> None:
        self._model_name = model_name
        self._batch_size = batch_size
        self._normalize = normalize
        self._model = None
        self._dimension: int | None = None
        self._lock = Lock()

    @property
    def name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._ensure_model()
        assert self._dimension is not None
        return self._dimension

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
            except ImportError as exc:  # pragma: no cover - environment dependent
                raise ConfigurationError(
                    "sentence-transformers is not installed. Install it with "
                    "`pip install sentence-transformers` or set "
                    "EMBEDDING_BACKEND=hashing."
                ) from exc
            logger.info("Loading embedding model", extra={"model": self._model_name})
            model = SentenceTransformer(self._model_name)
            self._model = model
            self._dimension = int(model.get_sentence_embedding_dimension())
            return model

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        return self._encode(list(texts))

    def embed_query(self, text: str) -> Vector:
        return self._encode([text])[0]

    def _encode(self, texts: list[str]) -> list[Vector]:
        if not texts:
            return []
        model = self._ensure_model()
        try:
            vectors = model.encode(
                texts,
                batch_size=self._batch_size,
                normalize_embeddings=self._normalize,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            return [list(map(float, v)) for v in vectors]
        except Exception as exc:  # noqa: BLE001
            logger.exception("Embedding failed")
            raise EmbeddingError("Failed to generate embeddings.") from exc
