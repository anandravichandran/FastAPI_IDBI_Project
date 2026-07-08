"""Port: large language model client."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.domain.entities import LLMMessage, LLMResult


class ILLMClient(ABC):
    """Generates chat completions from a sequence of messages."""

    @abstractmethod
    async def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        json_mode: bool = False,
    ) -> LLMResult:
        """Return a completion for ``messages``.

        Args:
            messages: Ordered conversation turns (system first by convention).
            json_mode: Ask the model to emit strict JSON when supported.
        """
        raise NotImplementedError

    async def aclose(self) -> None:  # pragma: no cover - optional cleanup hook
        """Release any network resources held by the client."""
        return None
