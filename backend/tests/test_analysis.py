from app.analysis.extract import (
    FindingsResult,
)
from app.analysis.qa import (
    answer_question,
)
from app.analysis.summarize import (
    SectionSummary,
    SummaryResult,
)
from app.retrieval.search import Citation


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    def generate_json(
        self,
        prompt: str,
        schema,
        system: str | None = None,
    ):
        self.calls += 1

        if schema is SectionSummary:
            return SectionSummary(
                section="abstract",
                summary="A section summary.",
            )

        if schema is SummaryResult:
            return SummaryResult(
                summary="A research summary.",
                problem="Classification.",
                approach="Transformer model.",
                main_result="91 percent accuracy.",
                limitations=[
                    "Small dataset."
                ],
            )

        if schema is FindingsResult:
            return FindingsResult(
                findings=[]
            )

        raise AssertionError(
            f"Unexpected schema: {schema}"
        )


def test_summary_uses_llm() -> None:
    llm = FakeLLM()

    from app.analysis.summarize import (
        summarize_paper,
    )

    result = summarize_paper(
        llm,
        [
            (
                "abstract",
                "This is the paper abstract.",
            )
        ],
    )

    assert result.summary == (
        "A research summary."
    )

    assert llm.calls == 2


def test_question_without_evidence_returns_not_found() -> None:
    result = answer_question(
        llm=FakeLLM(),
        question="What dataset was used?",
        citations=[],
    )

    assert result.answer == (
        "not found in the provided papers"
    )

    assert result.citations == []
    assert result.confidence == 0.0


class QALLM:
    def generate_json(
        self,
        prompt: str,
        schema,
        system: str | None = None,
    ):
        from app.analysis.qa import QAResult

        assert schema is QAResult

        return QAResult(
            answer="The model uses a transformer.",
            citations=[
                {
                    "paper_id": "paper-1",
                    "chunk_id": "paper-1:1",
                    "page": 4,
                    "section": "methods",
                }
            ],
            confidence=0.92,
        )


def test_question_preserves_valid_citation() -> None:
    citations = [
        Citation(
            paper_id="paper-1",
            chunk_id="paper-1:1",
            section="methods",
            page=4,
            text="The model uses a transformer.",
            score=0.91,
        )
    ]

    result = answer_question(
        llm=QALLM(),
        question="What model is used?",
        citations=citations,
    )

    assert (
        result.answer
        == "The model uses a transformer."
    )

    assert len(result.citations) == 1
    assert result.citations[0].page == 4

def test_long_section_is_summarized_without_truncation() -> None:
    llm = FakeLLM()

    from app.analysis.summarize import summarize_paper

    long_text = "Research content. " * 5000

    result = summarize_paper(
        llm,
        [
            (
                "methods",
                long_text,
            )
        ],
        max_section_chars=1000,
    )

    assert result.summary == "A research summary."
    assert llm.calls > 2