from __future__ import annotations

from pydantic import BaseModel, Field

from app.llm.base import LLMProvider
from app.llm.prompts import QA_PROMPT
from app.retrieval.search import Citation


class QACitation(BaseModel):
    paper_id: str
    chunk_id: str
    page: int
    section: str


class QAResult(BaseModel):
    answer: str
    citations: list[QACitation] = Field(
        default_factory=list
    )
    confidence: float = 0.0


def answer_question(
    llm: LLMProvider,
    question: str,
    citations: list[Citation],
) -> QAResult:
    if not citations:
        return QAResult(
            answer=(
                "not found in the provided papers"
            ),
            citations=[],
            confidence=0.0,
        )

    context = "\n\n".join(
        (
            f"[{item.paper_id}:{item.chunk_id}] "
            f"Page {item.page}, "
            f"Section: {item.section}\n"
            f"{item.text}"
        )
        for item in citations
    )

    prompt = (
        QA_PROMPT
        + "\n\nQuestion:\n"
        + question
        + "\n\nRetrieved evidence:\n"
        + context
    )

    result = llm.generate_json(
        prompt,
        QAResult,
    )

    allowed = {
        (
            item.paper_id,
            item.chunk_id,
        )
        for item in citations
    }

    result.citations = [
        citation
        for citation in result.citations
        if (
            citation.paper_id,
            citation.chunk_id,
        )
        in allowed
    ]

    if not result.citations:
        result.answer = (
            "not found in the provided papers"
        )
        result.confidence = 0.0

    return result