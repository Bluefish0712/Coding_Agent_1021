from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings


class DeepSeekError(RuntimeError):
    """An API or response error from DeepSeek."""


@dataclass(frozen=True)
class ChatResponse:
    message: dict[str, Any]
    finish_reason: str | None
    usage: dict[str, Any]


class DeepSeekClient:
    """Small client for DeepSeek's native OpenAI-compatible API."""

    def __init__(self, settings: Settings, http_client: httpx.Client | None = None):
        if not settings.api_key:
            raise DeepSeekError("DEEPSEEK_API_KEY is not configured")
        self.settings = settings
        self._client = http_client or httpx.Client(timeout=settings.timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] = "auto",
        temperature: float | None = None,
    ) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        if temperature is not None:
            payload["temperature"] = temperature

        try:
            response = self._client.post(
                f"{self.settings.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise DeepSeekError(f"request failed: {exc}") from exc

        if response.is_error:
            detail = response.text[:1000]
            raise DeepSeekError(f"DeepSeek HTTP {response.status_code}: {detail}")

        try:
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise DeepSeekError("DeepSeek returned an invalid chat response") from exc

        return ChatResponse(
            message=message,
            finish_reason=choice.get("finish_reason"),
            usage=data.get("usage", {}),
        )

