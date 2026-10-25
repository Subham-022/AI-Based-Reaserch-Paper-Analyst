import pytest
from pydantic import BaseModel

from app.llm.base import (
    LLMError,
    LLMProvider,
)


class Output(BaseModel):
    answer: str


class FakeLLM(LLMProvider):
    def __init__(
        self,
        responses: list[str],
    ) -> None:
        self.responses = responses
        self.calls = 0

    def generate(
        self,
        prompt: str,
        system: str | None = None,
    ) -> str:
        response = self.responses[
            min(
                self.calls,
                len(self.responses) - 1,
            )
        ]

        self.calls += 1

        return response


def test_generate_json_retries_once() -> None:
    client = FakeLLM(
        [
            "not json",
            '{"answer":"valid"}',
        ]
    )

    result = client.generate_json(
        "Answer the question.",
        Output,
    )

    assert result.answer == "valid"
    assert client.calls == 2


def test_generate_json_fails_after_retry() -> None:
    client = FakeLLM(
        [
            "invalid",
            "still invalid",
        ]
    )

    with pytest.raises(
        LLMError,
        match="invalid structured output",
    ):
        client.generate_json(
            "Answer the question.",
            Output,
        )

    assert client.calls == 2