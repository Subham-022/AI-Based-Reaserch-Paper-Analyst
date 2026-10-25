
from __future__ import annotations

from typing import Any

import httpx

from app.llm.base import LLMError, LLMProvider


class OllamaClient(LLMProvider):
    """Client for the local Ollama chat API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "llama3.2:3b",
        timeout: float = 300.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(
        self,
        prompt: str,
        system: str | None = None,
    ) -> str:
        """Generate a normal text response."""
        return self._chat(
            prompt=prompt,
            system=system,
            output_format=None,
        )

    def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str | None = None,
    ) -> str:
        """
        Ask Ollama to produce JSON conforming to a JSON Schema.

        Ollama supports `format: "json"` and a JSON Schema object.
        Passing the schema object is stricter than JSON mode alone.
        """
        return self._chat(
            prompt=prompt,
            system=system,
            output_format=schema,
        )

    def _chat(
        self,
        prompt: str,
        system: str | None,
        output_format: str | dict[str, Any] | None,
    ) -> str:
        messages: list[dict[str, str]] = []

        if system:
            messages.append(
                {
                    "role": "system",
                    "content": system.strip(),
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0,
            },
        }

        if output_format is not None:
            payload["format"] = output_format

        url = f"{self.base_url}/api/chat"

        print(f"USING OLLAMA: {self.base_url} MODEL={self.model}")
        print(f"OLLAMA REQUEST: {url}")
        print(f"OLLAMA STRUCTURED OUTPUT: {output_format is not None}")

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)

            response.raise_for_status()

        except httpx.TimeoutException as exc:
            raise LLMError(
                f"Ollama request timed out after {self.timeout} seconds. "
                "Check whether the model is still loading or generating."
            ) from exc

        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:2000]
            raise LLMError(
                f"Ollama returned HTTP {exc.response.status_code}: {body}"
            ) from exc

        except httpx.RequestError as exc:
            raise LLMError(
                f"Could not connect to Ollama at {self.base_url}: {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMError("Ollama returned an invalid HTTP JSON response.") from exc

        message = data.get("message")

        if not isinstance(message, dict):
            raise LLMError(
                f"Ollama response is missing its message object: {data}"
            )

        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise LLMError(
                f"Ollama returned an empty response. Details: {data}"
            )

        return content.strip()
