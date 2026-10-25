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