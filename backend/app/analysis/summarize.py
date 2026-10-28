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
    key_findings: list[str] = Field(default_factory=list)
    methodology_details: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    evaluation_metrics: list[str] = Field(default_factory=list)
    quantitative_results: list[str] = Field(default_factory=list)
    equations_and_calculations: list[str] = Field(default_factory=list)
    analysis_of_visuals_and_tables: list[str] = Field(default_factory=list)


_SECTION_PRIORITY = {
    "abstract": 0,
    "results": 1,
    "experiments": 2,
    "methods": 3,
    "methodology": 3,
    "conclusion": 4,
    "conclusions": 4,
    "discussion": 5,
    "introduction": 6,
}


def _build_summary_context(
    sections: list[tuple[str, str]],
    max_input_chars: int,
    max_section_chars: int,
) -> str:
    def base_name(name: str) -> str:
        return name.strip().lower().split(" (page ", maxsplit=1)[0]

    relevant_sections = [
        (name.strip(), text.strip())
        for name, text in sections
        if text.strip()
        and base_name(name) not in {"references", "reference"}
    ]
    relevant_sections.sort(
        key=lambda item: _SECTION_PRIORITY.get(
            base_name(item[0]),
            7,
        )
    )

    content: list[str] = []
    remaining = max_input_chars

    for name, text in relevant_sections:
        if remaining <= 0:
            break

        section_text = text[: min(max_section_chars, remaining)]
        content.append(f"{name}:\n{section_text}")
        remaining -= len(section_text)

    return "\n\n".join(content)


def summarize_paper(
    llm: LLMProvider,
    sections: list[tuple[str, str]],
    max_input_chars: int = 60000,
    max_section_chars: int = 12000,
    visual_context: str = "",
) -> SummaryResult:
    context = _build_summary_context(
        sections,
        max_input_chars=max_input_chars,
        max_section_chars=max_section_chars,
    )

    if not context:
        raise ValueError("No paper content is available to summarize.")

    return llm.generate_json(
        SUMMARY_PROMPT.format(
            sections=context,
            visual_context=(
                visual_context
                or "No tables or figure captions were extracted."
            ),
        ),
        SummaryResult,
        system=SUMMARY_SYSTEM,
    )
