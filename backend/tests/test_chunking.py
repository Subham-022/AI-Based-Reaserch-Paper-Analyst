from app.ingestion.sectioner import (
    Section,
    chunk_sections,
)


def test_long_section_uses_overlap() -> None:
    words = [
        f"word{i}"
        for i in range(250)
    ]

    text = " ".join(words)

    section = Section(
        name="results",
        text=text,
        start_page=5,
        end_page=5,
        page_parts=(
            (5, text),
        ),
    )

    chunks = chunk_sections(
        paper_id="paper-1",
        sections=[section],
        target_words=100,
        overlap_words=20,
    )

    assert len(chunks) == 3

    first_words = set(
        chunks[0].text.split()
    )

    second_words = set(
        chunks[1].text.split()
    )

    overlap = first_words.intersection(
        second_words
    )

    assert overlap


def test_chunk_has_hash() -> None:
    section = Section(
        name="abstract",
        text=(
            "This is an abstract containing "
            "enough words to produce a valid "
            "research paper chunk for testing."
        ),
        start_page=1,
        end_page=1,
        page_parts=(
            (
                1,
                (
                    "This is an abstract containing "
                    "enough words to produce a valid "
                    "research paper chunk for testing."
                ),
            ),
        ),
    )

    chunks = chunk_sections(
        paper_id="paper-1",
        sections=[section],
    )

    assert chunks
    assert len(
        chunks[0].content_hash
    ) == 64