from __future__ import annotations

from dataclasses import dataclass

import fitz
import pymupdf4llm


class ParserError(ValueError):
    """Raised when PDF text extraction fails."""


@dataclass(frozen=True)
class PageText:
    page: int
    text: str


@dataclass(frozen=True)
class ParsedDocument:
    pages: list[PageText]
    markdown: str


def parse_pdf(data: bytes) -> ParsedDocument:
    try:
        document = fitz.open(
            stream=data,
            filetype="pdf",
        )
    except Exception as exc:
        raise ParserError(
            "Unable to open the PDF."
        ) from exc

    pages: list[PageText] = []

    try:
        for index, page in enumerate(document):
            text = page.get_text("text")

            pages.append(
                PageText(
                    page=index + 1,
                    text=text,
                )
            )

        markdown = pymupdf4llm.to_markdown(
            document
        )

    except Exception as exc:
        raise ParserError(
            "Unable to extract text from the PDF."
        ) from exc

    finally:
        document.close()

    extracted_characters = sum(
        len(page.text.strip())
        for page in pages
    )

    if not pages or extracted_characters < 100:
        raise ParserError(
            "OCR_REQUIRED: this PDF contains "
            "insufficient extractable text. "
            "OCR is required for scanned PDFs."
        )

    return ParsedDocument(
        pages=pages,
        markdown=markdown,
    )