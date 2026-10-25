from app.ingestion.sectioner import (
    chunk_sections,
    detect_sections,
)


def test_detect_sections() -> None:
    pages = [
        (
            1,
            """
            A Research Paper

            ABSTRACT

            This is the abstract.

            1 Introduction

            This is the introduction.
            """,
        ),
        (
            2,
            """
            2 Methods

            The method is described here.

            3 Results

            The results are described here.
            """,
        ),
        (
            3,
            """
            4 Conclusion

            The conclusion is described here.
            """,
        ),
    ]

    sections = detect_sections(
        pages
    )

    names = [
        section.name
        for section in sections
    ]

    assert names == [
        "front matter",
        "abstract",
        "introduction",
        "methods",
        "results",
        "conclusion",
    ]

    methods = next(
        section
        for section in sections
        if section.name == "methods"
    )

    assert methods.start_page == 2
    assert methods.end_page == 2


def test_section_chunking_preserves_metadata() -> None:
    pages = [
        (
            1,
            """
            Methods

            This is a sufficiently long
            methodology description that
            contains enough words to be
            represented as a normal text
            chunk in the research paper.

            Table 1 | Metric | Score

            Accuracy | 0.91
            Precision | 0.89
            Recall | 0.87
            """,
        )
    ]

    sections = detect_sections(
        pages
    )

    chunks = chunk_sections(
        paper_id="paper-1",
        sections=sections,
        target_words=100,
        overlap_words=20,
    )

    assert chunks

    assert all(
        chunk.paper_id == "paper-1"
        for chunk in chunks
    )

    assert all(
        chunk.section == "methods"
        for chunk in chunks
    )

    assert any(
        chunk.content_type == "table"
        for chunk in chunks
    )