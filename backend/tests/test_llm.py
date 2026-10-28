import httpx
import pytest
from pydantic import BaseModel

from app.llm.base import LLMError, LLMProvider
from app.llm.ollama_client import OllamaClient


class Output(BaseModel):
    answer: str


class FakeLLM(LLMProvider):
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    def generate(
        self,
        prompt: str,
        system: str | None = None,
    ) -> str:
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


def test_generate_json_retries_once() -> None:
    client = FakeLLM(["not json", '{"answer":"valid"}'])

    result = client.generate_json("Answer the question.", Output)

    assert result.answer == "valid"
    assert client.calls == 2


def test_generate_json_fails_after_retry() -> None:
    client = FakeLLM(["invalid", "still invalid"])

    with pytest.raises(LLMError, match="invalid structured output"):
        client.generate_json("Answer the question.", Output)

    assert client.calls == 2


def test_generate_json_does_not_retry_provider_errors() -> None:
    class UnavailableLLM(FakeLLM):
        def generate(self, prompt: str, system: str | None = None) -> str:
            self.calls += 1
            raise LLMError("provider timed out")

    client = UnavailableLLM([])

    with pytest.raises(LLMError, match="provider timed out"):
        client.generate_json("Answer the question.", Output)

    assert client.calls == 1


def test_ollama_sends_chat_request_and_schema(monkeypatch) -> None:
    client = OllamaClient(model="test-model")
    request_data: dict = {}

    def fake_post(url: str, json: dict, timeout: float):
        request_data.update({"url": url, "json": json, "timeout": timeout})
        return httpx.Response(
            200,
            json={"message": {"content": '{"answer":"ok"}'}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}

    result = client.generate_structured("prompt", schema, "system")

    assert result == '{"answer":"ok"}'
    assert request_data["url"] == "http://127.0.0.1:11434/api/chat"
    assert request_data["json"]["model"] == "test-model"
    assert request_data["json"]["messages"][0] == {
        "role": "system",
        "content": "system",
    }
    assert request_data["json"]["format"] == schema


def test_ollama_connection_error_is_actionable(monkeypatch) -> None:
    def fail_post(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", fail_post)

    with pytest.raises(LLMError, match="Could not connect to Ollama"):
        OllamaClient().generate("prompt")


def test_ollama_rejects_empty_response(monkeypatch) -> None:
    def empty_response(url: str, **kwargs):
        return httpx.Response(
            200,
            json={"message": {"content": ""}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", empty_response)

    with pytest.raises(LLMError, match="empty response"):
        OllamaClient().generate("prompt")
