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


def test_question_attaches_retrieved_citation_when_llm_omits_it() -> None:
    from app.analysis.qa import QAResult

    class CitationOmittingLLM:
        def generate_json(
            self,
            prompt: str,
            schema,
            system: str | None = None,
        ):
            assert schema is QAResult
            return QAResult(
                answer="The model uses a transformer.",
                confidence=0.9,
            )

    citation = Citation(
        paper_id="paper-1",
        chunk_id="paper-1:1",
        section="methods",
        page=4,
        text="The model uses a transformer.",
        score=0.91,
    )

    result = answer_question(
        llm=CitationOmittingLLM(),
        question="What model is used?",
        citations=[citation],
    )

    assert isinstance(result, QAResult)
    assert result.answer == "The model uses a transformer."
    assert len(result.citations) == 1
    assert result.citations[0].paper_id == citation.paper_id
    assert result.citations[0].chunk_id == citation.chunk_id


def test_question_uses_retrieved_metadata_for_citations() -> None:
    from app.analysis.qa import QAResult

    class IncorrectCitationLLM:
        def generate_json(
            self,
            prompt: str,
            schema,
            system: str | None = None,
        ):
            assert schema is QAResult
            return QAResult(
                answer="The model uses a transformer.",
                citations=[
                    {
                        "paper_id": "paper-1",
                        "chunk_id": "paper-1:1",
                        "page": 999,
                        "section": "invented",
                    }
                ],
            )

    citation = Citation(
        paper_id="paper-1",
        chunk_id="paper-1:1",
        section="methods",
        page=4,
        text="The model uses a transformer.",
        score=0.91,
    )

    result = answer_question(
        llm=IncorrectCitationLLM(),
        question="What model is used?",
        citations=[citation],
    )

    assert len(result.citations) == 1
    assert result.citations[0].page == 4
    assert result.citations[0].section == "methods"


def test_question_replaces_unrelated_answer_with_relevant_evidence() -> None:
    from app.analysis.qa import QAResult

    class UnrelatedAnswerLLM:
        def generate_json(
            self,
            prompt: str,
            schema,
            system: str | None = None,
        ):
            assert schema is QAResult
            return QAResult(
                answer=(
                    "The model was trained on 2637 images and tested "
                    "on 660 images."
                ),
                citations=[
                    {
                        "paper_id": "paper-1",
                        "chunk_id": "paper-1:1",
                        "page": 14,
                        "section": "introduction",
                    }
                ],
                confidence=0.9,
            )

    citation = Citation(
        paper_id="paper-1",
        chunk_id="paper-1:1",
        section="introduction",
        page=14,
        text=(
            "The method achieved an accuracy of 88.95% and an "
            "F1-score of 0.909."
        ),
        score=0.91,
    )

    result = answer_question(
        llm=UnrelatedAnswerLLM(),
        question="What evaluation metrics and scores are reported?",
        citations=[citation],
    )

    assert "2637" not in result.answer
    assert "88.95%" in result.answer
    assert len(result.answer) < 500
    assert result.confidence == 0.0
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == citation.chunk_id


def test_question_fallback_extracts_only_relevant_sentences() -> None:
    from app.analysis.qa import QAResult
    from app.llm.base import LLMError

    class FailingLLM:
        def generate_json(self, prompt: str, schema, system: str | None = None):
            assert schema is QAResult
            raise LLMError("model timed out")

    citation = Citation(
        paper_id="paper-1",
        chunk_id="paper-1:1",
        section="results",
        page=7,
        text=(
            "The dataset contains 500 images. "
            "The model achieved 91% accuracy and an F1-score of 0.88. "
            "The authors used a convolutional neural network."
        ),
        score=0.91,
    )

    result = answer_question(
        llm=FailingLLM(),
        question="What accuracy metrics and scores are reported?",
        citations=[citation],
    )

    assert "91% accuracy" in result.answer
    assert "F1-score of 0.88" in result.answer
    assert "500 images" not in result.answer
    assert "convolutional neural network" not in result.answer
    assert len(result.citations) == 1


def test_question_falls_back_to_evidence_when_llm_fails() -> None:
    from app.analysis.qa import QAResult
    from app.llm.base import LLMError

    class FailingLLM:
        def generate_json(
            self,
            prompt: str,
            schema,
            system: str | None = None,
        ):
            assert schema is QAResult
            raise LLMError("model timed out")

    citation = Citation(
        paper_id="paper-1",
        chunk_id="paper-1:1",
        section="results",
        page=7,
        text="The model achieved 91% accuracy on the test set.",
        score=0.91,
    )

    result = answer_question(
        llm=FailingLLM(),
        question="What accuracy was achieved?",
        citations=[citation],
    )

    assert "91% accuracy" in result.answer
    assert result.confidence == 0.0
    assert len(result.citations) == 1
    assert result.citations[0].page == 7




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