
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Type

from pydantic import BaseModel, ValidationError


class LLMError(RuntimeError):
    """Raised when an LLM request or structured response fails."""


class LLMProvider(ABC):
    """Base interface shared by all LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, system: str | None = None) -> str:
        """Generate a text response."""
        raise NotImplementedError

    def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str | None = None,
    ) -> str:
        """
        Optional structured-output interface.

        Providers that support native JSON schema output can override this.
        Other providers continue using the normal generate() method.
        """
        schema_json = json.dumps(schema, ensure_ascii=False)
        instruction = (
            f"{prompt}\n\n"
            "Return exactly one JSON object containing actual answer values.\n"
            "Do not return the schema itself.\n"
            "Do not return descriptions, property definitions, or type definitions.\n"
            "Do not use Markdown or code fences.\n"
            "The required JSON schema is:\n"
            f"{schema_json}"
        )
        return self.generate(instruction, system=system)

    def generate_json(
        self,
        prompt: str,
        schema: Type[BaseModel],
        system: str | None = None,
    ) -> BaseModel:
        """
        Generate JSON and validate it against a Pydantic model.

        Attempts native structured output first, then retries with a
        correction instruction if the response is invalid.
        """
        json_schema = schema.model_json_schema()
        last_error: Exception | None = None
        last_raw = ""

        for attempt in range(2):
            instruction = (
                f"{prompt}\n\n"
                "Return exactly one JSON object containing the completed answer.\n"
                "Return actual values, not a JSON schema or schema description.\n"
                "Do not include Markdown, code fences, or explanatory text.\n"
                "Every required field must be present and have the correct type."
            )

            if attempt == 1:
                instruction += (
                    "\n\nYour previous response was invalid. "
                    "Correct the response and return only the completed JSON object."
                )

            try:
                # Prefer provider-native JSON Schema output when available.
                raw = self.generate_structured(
                    instruction,
                    schema=json_schema,
                    system=system,
                )
                last_raw = raw

                print(f"LLM RAW RESPONSE (attempt {attempt + 1}):")
                print(raw)

                cleaned = self._clean_json(raw)
                return schema.model_validate_json(cleaned)

            except ValidationError as exc:
                last_error = exc
                print("LLM VALIDATION ERROR:")
                print(exc)

            except LLMError:
                raise

            except ValueError as exc:
                last_error = exc
                print("LLM JSON ERROR:")
                print(exc)

        raw_preview = last_raw[:4000]
        raise LLMError(
            "The LLM returned invalid structured output. "
            f"Validation error: {last_error}. "
            f"Raw response: {raw_preview}"
        ) from last_error

    @staticmethod
    def _clean_json(raw: str) -> str:
        """Remove Markdown fences and isolate the returned JSON object."""
        text = raw.strip()

        if text.startswith("```"):
            lines = text.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            text = "\n".join(lines).strip()

        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end < start:
            raise ValueError("The LLM response does not contain a JSON object.")

        return text[start : end + 1]
