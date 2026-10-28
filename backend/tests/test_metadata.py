from app.ingestion.metadata import (
    extract_metadata,
)


def test_metadata_extracts_common_fields() -> None:
    pages = [
        """
        Deep Learning for Research

        Alice Smith, Bob Jones

        Journal of Artificial Intelligence Research

        2025

        DOI: 10.1234/example.1
        """
    ]

    metadata = extract_metadata(
        pages,
        source_url=(
            "https://arxiv.org/abs/"
            "2501.12345"
        ),
    )

    assert metadata.title == (
        "Deep Learning for Research"
    )

    assert metadata.authors == [
        "Alice Smith",
        "Bob Jones",
    ]

    assert metadata.venue == (
        "Journal of Artificial Intelligence Research"
    )

    assert metadata.year == 2025

    assert metadata.doi == (
        "10.1234/example.1"
    )

    assert metadata.arxiv_id == (
        "2501.12345"
    )


def test_metadata_extracts_fields_from_page_text_and_pdf_properties() -> None:
    metadata = extract_metadata(
        [
            "A Detailed Study of Research Systems\n"
            "Alice Smith; Bob Jones\n"
            "Proceedings of Example Conference\n"
            "2024\n"
            "DOI: 10.1234/example.2",
        ],
        source_url="https://arxiv.org/abs/2401.12345",
        pdf_metadata={
            "title": "",
            "author": "Alice Smith; Bob Jones",
        },
        fallback_title="paper-file",
    )

    assert metadata.title == "A Detailed Study of Research Systems"
    assert metadata.authors == ["Alice Smith", "Bob Jones"]
    assert metadata.venue == "Proceedings of Example Conference"
    assert metadata.year == 2024
    assert metadata.doi == "10.1234/example.2"
    assert metadata.arxiv_id == "2401.12345"


def test_metadata_uses_embedded_title_and_filename_fallback() -> None:
    embedded = extract_metadata(
        ["Short title"],
        pdf_metadata={"title": "PDF Document Title"},
    )
    fallback = extract_metadata(
        ["Short"],
        fallback_title="research-paper",
    )

    assert embedded.title == "PDF Document Title"
    assert fallback.title == "research-paper"