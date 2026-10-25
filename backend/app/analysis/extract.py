from __future__ import annotations

from pydantic import BaseModel, Field

from app.llm.base import LLMProvider
from app.llm.prompts import (
    FINDINGS_PROMPT,
    LIMITATIONS_PROMPT,
    METHODOLOGY_PROMPT,
)


class Finding(BaseModel):
    finding: str
    evidence: str
    page: int


class FindingsResult(BaseModel):
    findings: list[Finding] = Field(
        default_factory=list
    )


class Evidence(BaseModel):
    text: str
    page: int


class MethodologyResult(BaseModel):
    method: str
    models: list[str] = Field(
        default_factory=list
    )
    datasets: list[str] = Field(
        default_factory=list
    )
    metrics: list[str] = Field(
        default_factory=list
    )
    experimental_setup: str
    evidence: list[Evidence] = Field(
        default_factory=list
    )


class Limitation(BaseModel):
    text: str
    type: str
    page: int


class LimitationsResult(BaseModel):
    limitations: list[Limitation] = Field(
        default_factory=list
    )


def extract_findings(
    llm: LLMProvider,
    content: str,
) -> FindingsResult:
    prompt = (
        FINDINGS_PROMPT
        + "\n\nPaper content:\n"
        + content
    )

    return llm.generate_json(
        prompt,
        FindingsResult,
    )


def analyze_methodology(
    llm: LLMProvider,
    content: str,
) -> MethodologyResult:
    prompt = (
        METHODOLOGY_PROMPT
        + "\n\nPaper content:\n"
        + content
    )

    return llm.generate_json(
        prompt,
        MethodologyResult,
    )


def extract_limitations(
    llm: LLMProvider,
    content: str,
) -> LimitationsResult:
    prompt = (
        LIMITATIONS_PROMPT
        + "\n\nPaper content:\n"
        + content
    )

    return llm.generate_json(
        prompt,
        LimitationsResult,
    )