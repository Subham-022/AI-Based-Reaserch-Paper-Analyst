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
        return self._chat(prompt, system, output_format=None)

    def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str | None = None,
    ) -> str:
        return self._chat(prompt, system, output_format=schema)

    def _chat(
        self,
        prompt: str,
        system: str | None,
        output_format: str | dict[str, Any] | None,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append(
                {"role": "system", "content": system.strip()}
            )
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0},
        }
        if output_format is not None:
            payload["format"] = output_format

        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            raise LLMError(
                f"Ollama request timed out after {self.timeout} seconds. "
                "Check whether the model is loaded and try again."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMError(
                f"Ollama returned HTTP {exc.response.status_code}: "
                f"{exc.response.text[:1000]}"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMError(
                f"Could not connect to Ollama at {self.base_url}. "
                "Start Ollama and try again."
            ) from exc
        except ValueError as exc:
            raise LLMError(
                "Ollama returned an invalid HTTP JSON response."
            ) from exc

        message = data.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise LLMError("Ollama returned an empty response.")

        return content.strip()
