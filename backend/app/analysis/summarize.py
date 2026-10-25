from __future__ import annotations

from pydantic import BaseModel, Field

from app.llm.base import LLMProvider
from app.llm.prompts import SUMMARY_PROMPT, SUMMARY_SYSTEM


class SummaryResult(BaseModel):
    summary: str
    problem: str
    approach: str
    main_result: str
    limitations: list[str] = Field(default_factory=list)


class SectionSummary(BaseModel):
    section: str
    summary: str


def _split_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = min(start + max_chars, len(text))

        if end < len(text):
            split_at = text.rfind(" ", start, end)
            if split_at > start:
                end = split_at

        chunks.append(text[start:end].strip())
        start = end

    return [chunk for chunk in chunks if chunk]


def _summarize_chunk(
    llm: LLMProvider,
    section: str,
    text: str,
) -> SectionSummary:
    prompt = f"""
Summarize this research paper section.

Section:
{section}

Content:
{text}
"""

    return llm.generate_json(
        prompt,
        SectionSummary,
        system=SUMMARY_SYSTEM,
    )


def _summarize_long_section(
    llm: LLMProvider,
    section: str,
    text: str,
    max_chars: int,
) -> SectionSummary:
    chunks = _split_text(text, max_chars)

    chunk_summaries = [
        _summarize_chunk(llm, section, chunk)
        for chunk in chunks
    ]

    combined = "\n\n".join(
        item.summary for item in chunk_summaries
    )

    prompt = f"""
Create one coherent summary of the following partial summaries
from the "{section}" section of a research paper.

Partial summaries:
{combined}

Do not add information that is not present in the partial summaries.
"""

    return llm.generate_json(
        prompt,
        SectionSummary,
        system=SUMMARY_SYSTEM,
    )


def summarize_sections(
    llm: LLMProvider,
    sections: list[tuple[str, str]],
    max_section_chars: int = 12000,
) -> list[SectionSummary]:
    results: list[SectionSummary] = []

    for name, text in sections:
        if len(text) <= max_section_chars:
            result = _summarize_chunk(
                llm,
                name,
                text,
            )
        else:
            result = _summarize_long_section(
                llm,
                name,
                text,
                max_section_chars,
            )

        results.append(result)

    return results


def summarize_paper(
    llm: LLMProvider,
    sections: list[tuple[str, str]],
    max_section_chars: int = 12000,
) -> SummaryResult:
    section_summaries = summarize_sections(
        llm,
        sections,
        max_section_chars=max_section_chars,
    )

    combined = "\n\n".join(
        f"{item.section}: {item.summary}"
        for item in section_summaries
    )

    prompt = SUMMARY_PROMPT.format(
        sections=combined,
    )

    return llm.generate_json(
        prompt,
        SummaryResult,
        system=SUMMARY_SYSTEM,
    )