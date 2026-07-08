"""Cache port."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ICache(ABC):
    """A minimal TTL cache abstraction used by the service layer."""

    @abstractmethod
    def get(self, key: str) -> Any | None: ...

    @abstractmethod
    def set(self, key: str, value: Any, *, ttl: float) -> None: ...

    @abstractmethod
    def invalidate(self, key: str) -> None: ...

    @abstractmethod
    def clear(self) -> None: ...

    @abstractmethod
    def stats(self) -> dict[str, Any]: ...
