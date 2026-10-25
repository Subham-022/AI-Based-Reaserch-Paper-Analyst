from __future__ import annotations

import os

from openai import OpenAI
from openai import APIError
from openai import APIConnectionError
from openai import APITimeoutError

from app.llm.base import LLMError, LLMProvider


class OpenAICompatibleClient(LLMProvider):
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
            "gpt-4o-mini",
        )
        self.base_url = (
            base_url
            or os.getenv(
                "LLM_BASE_URL",
                "https://api.openai.com/v1",
            )
        ).rstrip("/")

        if not self.api_key:
            raise LLMError(
                "LLM_API_KEY is required for the OpenAI-compatible provider."
            )

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
        )

    def generate(
        self,
        prompt: str,
        system: str | None = None,
    ) -> str:
        messages: list[dict[str, str]] = []

        if system:
            messages.append(
                {
                    "role": "system",
                    "content": system,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
        except (
            APIError,
            APIConnectionError,
            APITimeoutError,
        ) as exc:
            raise LLMError(
                "The OpenAI-compatible API request failed."
            ) from exc

        if not response.choices:
            raise LLMError(
                "The OpenAI-compatible API returned no choices."
            )

        content = response.choices[0].message.content

        if not content:
            raise LLMError(
                "The OpenAI-compatible API returned empty content."
            )

        return content.strip()