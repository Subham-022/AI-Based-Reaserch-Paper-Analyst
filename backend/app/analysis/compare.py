from __future__ import annotations

from pydantic import BaseModel, Field

from app.llm.base import LLMProvider
from app.llm.prompts import COMPARISON_PROMPT


class SourceCitation(BaseModel):
    paper_id: str
    chunk_id: str
    page: int


class ComparisonCell(BaseModel):
    value: str
    citations: list[SourceCitation] = Field(
        default_factory=list
    )


class PaperComparison(BaseModel):
    paper_id: str
    problem: ComparisonCell
    method: ComparisonCell
    dataset: ComparisonCell
    metrics: ComparisonCell
    results: ComparisonCell
    limitations: ComparisonCell


class ComparisonResult(BaseModel):
    papers: list[PaperComparison]


def compare_papers(
    llm: LLMProvider,
    papers: dict[str, str],
) -> ComparisonResult:
    formatted = "\n\n".join(
        f"===== PAPER {paper_id} =====\n{content}"
        for paper_id, content in papers.items()
    )

    prompt = COMPARISON_PROMPT + (
        "\n\nPaper contents:\n"
        + formatted
    )

    return llm.generate_json(
        prompt,
        ComparisonResult,
    )