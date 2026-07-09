"""DeepSeek V3 implementation of :class:`ILLMClient`.

DeepSeek exposes an OpenAI-compatible ``/chat/completions`` endpoint. This
adapter talks to it over an async ``httpx`` client with retry-free, bounded
timeouts. Any transport or protocol failure is surfaced as
:class:`LLMError`, letting the service layer decide whether to fall back to a
deterministic explanation.
"""
from __future__ import annotations

import asyncio
from collections.abc import Sequence

import httpx

from common.resilience.http_client import build_async_client
from advisor.core.config import Settings
from advisor.core.exceptions import LLMError
from advisor.core.logging import get_logger
from advisor.domain.entities import LLMMessage, LLMResult
from advisor.domain.interfaces.llm import ILLMClient

logger = get_logger(__name__)


class DeepSeekLLMClient(ILLMClient):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: httpx.AsyncClient | None = None
        # Guards lazy client creation (see NvidiaLLMClient).
        self._lock = asyncio.Lock()

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    self._client = build_async_client(
                        base_url=self._settings.deepseek_base_url.rstrip("/"),
                        timeout_seconds=self._settings.deepseek_timeout_seconds,
                        headers={
                            "Authorization": f"Bearer {self._settings.deepseek_api_key}",
                            "Content-Type": "application/json",
                        },
                    )
        return self._client

    async def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        json_mode: bool = False,
    ) -> LLMResult:
        if not self._settings.deepseek_api_key:
            raise LLMError("DeepSeek API key is not configured.")

        payload: dict[str, object] = {
            "model": self._settings.deepseek_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": self._settings.deepseek_temperature,
            "max_tokens": self._settings.deepseek_max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            client = await self._http()
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "DeepSeek returned an error status",
                extra={"status_code": exc.response.status_code},
            )
            raise LLMError(
                "DeepSeek returned an error status.",
                details={"status_code": exc.response.status_code},
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("DeepSeek request failed", extra={"error": str(exc)})
            raise LLMError("Failed to reach DeepSeek.") from exc

        try:
            choice = data["choices"][0]
            usage = data.get("usage", {})
            return LLMResult(
                content=choice["message"]["content"],
                model=data.get("model", self._settings.deepseek_model),
                finish_reason=choice.get("finish_reason"),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("DeepSeek response had an unexpected shape.") from exc

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
