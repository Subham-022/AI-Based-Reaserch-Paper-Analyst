from app.ingestion.cleaner import (
    clean_pages,
)


def test_clean_pages_removes_repeated_headers() -> None:
    pages = [
        (
            "Research Paper Title\n"
            "1\n"
            "Abstract\n"
            "Useful content."
        ),
        (
            "Research Paper Title\n"
            "2\n"
            "Methods\n"
            "More useful content."
        ),
        (
            "Research Paper Title\n"
            "3\n"
            "Results\n"
            "Final useful content."
        ),
    ]

    cleaned = clean_pages(pages)

    assert len(cleaned) == 3

    assert all(
        "Research Paper Title"
        not in page
        for page in cleaned
    )

    assert all(
        not any(
            line.strip().isdigit()
            for line in page.splitlines()
        )
        for page in cleaned
    )

    assert "Useful content." in cleaned[0]

    assert "More useful content." in (
        cleaned[1]
    )

    assert "Final useful content." in (
        cleaned[2]
    )