import sys
import types

import fitz
import pytest


fake_pymupdf4llm = types.SimpleNamespace(
    to_markdown=lambda document: (
        "\n\n".join(
            page.get_text("text")
            for page in document
        )
    )
)

sys.modules.setdefault(
    "pymupdf4llm",
    fake_pymupdf4llm,
)

from app.ingestion.parser import (
    ParserError,
    parse_pdf,
)


def _create_pdf(
    text: str | None = None,
) -> bytes:
    document = fitz.open()

    page = document.new_page()

    if text:
        page.insert_text(
            (72, 72),
            text,
        )

    data = document.tobytes()

    document.close()

    return data


def test_parser_extracts_text() -> None:
    text = (
        "This is a research paper. "
        "It contains enough extractable "
        "text to pass the scanned document "
        "detection threshold. "
    ) * 5

    data = _create_pdf(text)

    parsed = parse_pdf(data)

    assert len(parsed.pages) == 1
    assert "research paper" in (
        parsed.pages[0].text
    )
    assert "research paper" in (
        parsed.markdown
    )


def test_parser_detects_scanned_pdf() -> None:
    data = _create_pdf()

    with pytest.raises(
        ParserError,
        match="OCR_REQUIRED",
    ):
        parse_pdf(data)