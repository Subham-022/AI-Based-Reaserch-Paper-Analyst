from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

from app.llm.base import LLMError, LLMProvider
from app.llm.prompts import QA_PROMPT
from app.retrieval.search import Citation

logger = logging.getLogger(__name__)


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


_QUESTION_STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "at",
    "by",
    "do",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "paper",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


def _terms(text: str) -> set[str]:
    terms = set(re.findall(r"\b[a-z0-9]+\b", text.casefold()))
    return {
        term[:-1] if len(term) > 4 and term.endswith("s") else term
        for term in terms
    }


def _numbers(text: str) -> set[str]:
    return {
        number.rstrip("%")
        for number in re.findall(r"\b\d+(?:\.\d+)?%?\b", text)
    }


def _question_evidence_terms(question: str) -> set[str]:
    terms = _terms(question) - _QUESTION_STOP_WORDS
    if terms.intersection(
        {"evaluation", "metric", "performance", "score"}
    ):
        terms.update(
            {
                "accuracy",
                "auc",
                "f1",
                "precision",
                "recall",
                "sensitivity",
                "specificity",
            }
        )
    return terms


def _answer_is_relevant(
    question: str,
    answer: str,
    citations: list[Citation],
) -> bool:
    question_terms = _question_evidence_terms(question)
    answer_terms = _terms(answer)
    if question_terms and not question_terms.intersection(answer_terms):
        return False

    evidence = " ".join(item.text for item in citations)
    return _numbers(answer).issubset(_numbers(evidence))


def _evidence_fallback(
    question: str,
    citations: list[Citation],
    message: str = (
        "I couldn't verify a direct answer from the generated response."
    ),
) -> QAResult:
    question_terms = _question_evidence_terms(question)
    ranked_sentences: list[tuple[int, int, Citation, str]] = []

    for source_index, item in enumerate(citations):
        for sentence in re.split(r"(?<=[.!?])\s+|[\r\n]+", item.text):
            sentence = sentence.strip()
            overlap = question_terms.intersection(_terms(sentence))
            if overlap:
                ranked_sentences.append(
                    (len(overlap), source_index, item, sentence)
                )

    ranked_sentences.sort(key=lambda result: (-result[0], result[1]))
    excerpts: list[str] = []
    selected_sources: list[Citation] = []
    seen_sentences: set[str] = set()

    for _score, _source_index, item, sentence in ranked_sentences[:4]:
        normalized_sentence = sentence.casefold()
        if normalized_sentence in seen_sentences:
            continue
        seen_sentences.add(normalized_sentence)
        if item not in selected_sources:
            selected_sources.append(item)
        excerpt = sentence[:350].rstrip()
        if len(sentence) > 350:
            excerpt += "..."
        excerpts.append(f"Page {item.page} ({item.section}): {excerpt}")

    if not excerpts:
        selected_sources = citations[:1]
        excerpts = [
            f"Page {item.page} ({item.section}): {item.text[:350].rstrip()}"
            for item in selected_sources
        ]
    return QAResult(
        answer=(
            f"{message} Relevant retrieved passages:\n\n"
            + "\n\n".join(excerpts)
        ),
        citations=[
            QACitation(
                paper_id=item.paper_id,
                chunk_id=item.chunk_id,
                page=item.page,
                section=item.section,
            )
            for item in selected_sources
        ],
        confidence=0.0,
    )


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

    try:
        result = llm.generate_json(
            prompt,
            QAResult,
        )
    except LLMError as exc:
        logger.warning(
            "Chat answer generation failed (%s); returning retrieved evidence.",
            exc,
        )
        return _evidence_fallback(
            question,
            citations,
            message=(
                "The language model was unavailable or timed out."
            ),
        )

    retrieved_by_id = {
        (item.paper_id, item.chunk_id): item
        for item in citations
    }

    if result.answer.strip().casefold() == (
        "not found in the provided papers"
    ):
        result.citations = []
        result.confidence = 0.0
        return result

    if not _answer_is_relevant(
        question,
        result.answer,
        citations,
    ):
        return _evidence_fallback(question, citations)

    verified_citations: list[QACitation] = []
    seen: set[tuple[str, str]] = set()

    for citation in result.citations:
        key = (citation.paper_id, citation.chunk_id)
        source = retrieved_by_id.get(key)

        if source is None or key in seen:
            continue

        seen.add(key)
        verified_citations.append(
            QACitation(
                paper_id=source.paper_id,
                chunk_id=source.chunk_id,
                page=source.page,
                section=source.section,
            )
        )

    result.citations = verified_citations

    if not result.citations:
        result.citations = [
            QACitation(
                paper_id=item.paper_id,
                chunk_id=item.chunk_id,
                page=item.page,
                section=item.section,
            )
            for item in citations[:3]
        ]

    return result