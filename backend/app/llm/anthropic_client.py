from __future__ import annotations

import os

import httpx

from app.llm.base import LLMError, LLMProvider


class AnthropicClient(LLMProvider):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = model or os.getenv(
            "LLM_MODEL",
            "claude-3-5-haiku-latest",
        )
        self.base_url = (
            base_url
            or os.getenv(
                "LLM_BASE_URL",
                "https://api.anthropic.com",
            )
        ).rstrip("/")
        self.timeout = timeout

        if not self.api_key:
            raise LLMError(
                "LLM_API_KEY is required for the Anthropic provider."
            )

    def generate(
        self,
        prompt: str,
        system: str | None = None,
    ) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload: dict[str, object] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }

        if system:
            payload["system"] = system

        try:
            response = httpx.post(
                f"{self.base_url}/v1/messages",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(
                "The Anthropic API request failed."
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMError(
                "The Anthropic API returned invalid JSON."
            ) from exc

        content = data.get("content", [])

        if not isinstance(content, list) or not content:
            raise LLMError(
                "The Anthropic API returned no content."
            )

        text_parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict)
            and item.get("type") == "text"
        ]

        result = "\n".join(
            part for part in text_parts if part
        ).strip()

        if not result:
            raise LLMError(
                "The Anthropic API returned empty content."
            )

        return result