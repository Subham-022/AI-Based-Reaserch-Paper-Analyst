import sys
import types

import fitz
import pytest


fake_pymupdf4llm = types.SimpleNamespace(
    to_markdown=lambda document, **kwargs: (
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

from app.ingestion.parser import (  # noqa: E402
    ParserError,
    extract_figure_image,
    parse_pdf,
)


def _create_pdf(
    text: str | None = None,
    metadata: dict[str, str] | None = None,
) -> bytes:
    document = fitz.open()

    page = document.new_page()

    if text:
        page.insert_text(
            (72, 72),
            text,
        )

    if metadata:
        document.set_metadata(metadata)

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


def test_parser_returns_embedded_pdf_metadata() -> None:
    text = (
        "This paper has enough extractable text to pass "
        "the scanned document detection threshold. "
    ) * 5

    parsed = parse_pdf(
        _create_pdf(
            text,
            {"title": "PDF metadata title", "author": "A. Author"},
        )
    )

    assert parsed.metadata["title"] == "PDF metadata title"
    assert parsed.metadata["author"] == "A. Author"


def test_parser_detects_scanned_pdf() -> None:
    data = _create_pdf()

    with pytest.raises(
        ParserError,
        match="OCR_REQUIRED",
    ):
        parse_pdf(data)


def test_parser_extracts_vector_figure_and_calculation() -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        (
            "This research paper contains sufficient text for extraction. "
            "The embedded image illustrates a scientific result."
        ),
    )
    page.insert_text(
        (72, 92),
        "Figure 1: Example classification curve",
    )
    page.insert_text(
        (72, 112),
        "The area under the curve was AUC = 0.94.",
    )
    page.draw_line((72, 110), (260, 200), color=(0, 0, 1), width=2)
    page.draw_line((72, 200), (260, 110), color=(1, 0, 0), width=2)
    data = document.tobytes()
    document.close()

    parsed = parse_pdf(data)

    assert len(parsed.figures) == 1
    assert parsed.figures[0].page == 1
    assert parsed.figures[0].xref == 0
    assert parsed.figures[0].caption == (
        "Figure 1 Example classification curve"
    )
    assert any("AUC = 0.94" in item.text for item in parsed.equations)

    image, media_type = extract_figure_image(data, 1, 0)
    assert media_type == "image/png"
    assert image.startswith(b"\x89PNG")


def test_parser_extracts_embedded_pdf_image() -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        (
            "This research paper contains sufficient text for extraction. "
            "The embedded image illustrates a scientific result."
        ),
    )
    page.insert_text((72, 92), "Figure 1: Embedded image example")
    pixmap = fitz.Pixmap(
        fitz.csRGB,
        fitz.IRect(0, 0, 16, 16),
        False,
    )
    pixmap.clear_with(255)
    page.insert_image(
        fitz.Rect(72, 110, 120, 158),
        pixmap=pixmap,
    )
    data = document.tobytes()
    document.close()

    parsed = parse_pdf(data)
    embedded = next(figure for figure in parsed.figures if figure.xref > 0)

    image, media_type = extract_figure_image(
        data,
        embedded.page,
        embedded.xref,
    )

    assert media_type == "image/png"
    assert image.startswith(b"\x89PNG")


def test_parser_renders_uncaptioned_vector_graph() -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        (
            "This research paper contains sufficient text for extraction. "
            "The figure has no caption but contains a plotted graph."
        ),
    )
    for offset in range(5):
        page.draw_line(
            (100 + offset * 40, 140),
            (140 + offset * 40, 620),
            color=(0, 0, 1),
            width=2,
        )
    data = document.tobytes()
    document.close()

    parsed = parse_pdf(data)

    preview = next(figure for figure in parsed.figures if figure.xref == 0)
    assert preview.caption == "Vector graphic preview (page 1)"

    image, media_type = extract_figure_image(data, 1, 0)
    assert media_type == "image/png"
    assert image.startswith(b"\x89PNG")
