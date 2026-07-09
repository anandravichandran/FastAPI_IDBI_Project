"""NVIDIA NIM implementation of :class:`ILLMClient`.

NVIDIA's hosted inference endpoint (``https://integrate.api.nvidia.com/v1``)
exposes an OpenAI-compatible ``/chat/completions`` endpoint serving models
such as ``deepseek-ai/deepseek-v4-pro``. This adapter talks to it over an
async ``httpx`` client with retry-free, bounded timeouts, mirroring
:class:`DeepSeekLLMClient`. Any transport or protocol failure is surfaced as
:class:`LLMError`, letting the service layer decide whether to fall back to a
deterministic explanation.
"""
from __future__ import annotations

from collections.abc import Sequence

import httpx

from coach.core.config import Settings
from coach.core.exceptions import LLMError
from coach.core.logging import get_logger
from coach.domain.entities import LLMMessage, LLMResult
from coach.domain.interfaces.llm import ILLMClient

logger = get_logger(__name__)


class NvidiaLLMClient(ILLMClient):
    """Calls NVIDIA's OpenAI-compatible chat completions endpoint."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.nvidia_base_url.rstrip("/"),
                timeout=httpx.Timeout(self._settings.nvidia_timeout_seconds),
                headers={
                    "Authorization": f"Bearer {self._settings.nvidia_api_key}",
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
        if not self._settings.nvidia_api_key:
            raise LLMError("NVIDIA API key is not configured.")

        payload: dict[str, object] = {
            "model": self._settings.nvidia_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": self._settings.nvidia_temperature,
            "top_p": self._settings.nvidia_top_p,
            "max_tokens": self._settings.nvidia_max_tokens,
            "stream": False,
            "chat_template_kwargs": {"thinking": self._settings.nvidia_thinking},
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = await self._http().post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "NVIDIA returned an error status",
                extra={"status_code": exc.response.status_code},
            )
            raise LLMError(
                "NVIDIA returned an error status.",
                details={"status_code": exc.response.status_code},
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("NVIDIA request failed", extra={"error": str(exc)})
            raise LLMError("Failed to reach NVIDIA.") from exc

        try:
            choice = data["choices"][0]
            usage = data.get("usage", {})
            return LLMResult(
                content=choice["message"]["content"],
                model=data.get("model", self._settings.nvidia_model),
                finish_reason=choice.get("finish_reason"),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("NVIDIA response had an unexpected shape.") from exc

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
