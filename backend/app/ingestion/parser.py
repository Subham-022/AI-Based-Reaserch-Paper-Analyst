from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass

import fitz
import pymupdf4llm


_FIGURE_CAPTION_RE = re.compile(
    r"^\s*((?:figure|fig\.?)\s*\d+[a-z]?)\s*[:.]?\s*(.*)$",
    re.IGNORECASE,
)
_TABLE_CAPTION_RE = re.compile(
    r"^\s*(table\s*\d+[a-z]?)\s*[:.]?\s*(.*)$",
    re.IGNORECASE,
)
_CALCULATION_RE = re.compile(
    r"(?:=|≈|≃|≤|≥|±|×|÷|∑|∫|√|"
    r"\b(?:accuracy|precision|recall|f1(?:-score)?|auc|"
    r"sensitivity|specificity|loss)\s*(?:of|=|:))",
    re.IGNORECASE,
)


class ParserError(ValueError):
    """Raised when PDF text extraction fails."""


@dataclass(frozen=True)
class PageText:
    page: int
    text: str


@dataclass(frozen=True)
class FigureAsset:
    page: int
    xref: int
    caption: str


@dataclass(frozen=True)
class ExtractedTable:
    page: int
    caption: str
    rows: list[list[str]]
    preview_only: bool = False


@dataclass(frozen=True)
class ExtractedEquation:
    page: int
    text: str


@dataclass(frozen=True)
class ParsedDocument:
    pages: list[PageText]
    markdown: str
    metadata: dict[str, str | None]
    figures: list[FigureAsset]
    tables: list[ExtractedTable]
    equations: list[ExtractedEquation]


def _is_reliable_table(
    bbox: tuple[float, float, float, float],
    rows: list[list[str]],
    page: fitz.Page,
) -> bool:
    if len(rows) < 2 or len(rows) > 40:
        return False

    column_count = max((len(row) for row in rows), default=0)
    if column_count < 2 or column_count > 12:
        return False

    page_area = page.rect.get_area()
    table_area = fitz.Rect(bbox).get_area()
    if page_area <= 0 or table_area / page_area > 0.55:
        return False

    cells = [cell for row in rows for cell in row]
    nonempty_cells = [cell for cell in cells if cell]
    if len(nonempty_cells) < 3 or len(nonempty_cells) / len(cells) < 0.45:
        return False

    if sum(map(len, nonempty_cells)) / len(nonempty_cells) > 120:
        return False

    return True


def _clean_table_cell(value: object) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"[-–—_]{2,}", text):
        return ""
    return text


def _table_is_near_caption(
    bbox: tuple[float, float, float, float],
    captions: list[str],
    page: fitz.Page,
) -> bool:
    if not captions:
        return True

    table_rect = fitz.Rect(bbox)
    for caption in captions:
        label = " ".join(caption.split()[:2]).rstrip(".:")
        matches = page.search_for(label)
        if matches and any(
            -24 <= table_rect.y0 - match.y1 <= 160
            for match in matches
        ):
            return True
    return False


def _extract_page_assets(
    page: fitz.Page,
    page_number: int,
) -> tuple[
    list[FigureAsset],
    list[ExtractedTable],
    list[ExtractedEquation],
]:
    page_text = page.get_text("text")
    figure_captions: list[str] = []
    table_captions: list[str] = []
    equations: list[ExtractedEquation] = []

    for line in page_text.splitlines():
        text = line.strip()
        if not text:
            continue

        figure_match = _FIGURE_CAPTION_RE.match(text)
        if figure_match:
            figure_captions.append(
                " ".join(
                    part for part in figure_match.groups() if part
                ).strip()
            )

        table_match = _TABLE_CAPTION_RE.match(text)
        if table_match:
            table_captions.append(
                " ".join(
                    part for part in table_match.groups() if part
                ).strip()
            )

        if _CALCULATION_RE.search(text) and len(text) <= 1200:
            equations.append(
                ExtractedEquation(
                    page=page_number,
                    text=text,
                )
            )

    image_xrefs = list(
        dict.fromkeys(
            image[0]
            for image in page.get_images(full=True)
            if image and image[0] > 0
        )
    )
    figures = [
        FigureAsset(
            page=page_number,
            xref=xref,
            caption=(
                figure_captions[index]
                if index < len(figure_captions)
                else f"Image extracted from page {page_number}"
            ),
        )
        for index, xref in enumerate(image_xrefs)
    ]

    if figure_captions or _has_vector_visual(page):
        previews = figure_captions or [
            f"Vector graphic preview (page {page_number})"
        ]
        figures.extend(
            FigureAsset(
                page=page_number,
                xref=0,
                caption=caption,
            )
            for caption in previews
        )

    table_candidates = []
    for strategy in ("lines", "text"):
        try:
            found_tables = page.find_tables(strategy=strategy)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            continue
        table_candidates.extend(found_tables.tables)

    tables: list[ExtractedTable] = []
    accepted_captions: set[int] = set()
    accepted_bboxes: list[fitz.Rect] = []
    for index, table in enumerate(table_candidates):
        rows = [
            [_clean_table_cell(cell) for cell in row]
            for row in table.extract()
        ]
        rows = [row for row in rows if any(row)]
        table_rect = fitz.Rect(table.bbox)
        if (
            not table_captions
            or not _table_is_near_caption(
                table.bbox,
                table_captions,
                page,
            )
            or not _is_reliable_table(table.bbox, rows, page)
            or any(table_rect == previous for previous in accepted_bboxes)
        ):
            continue

        accepted_bboxes.append(table_rect)
        caption_index = min(len(tables), len(table_captions) - 1)
        if table_captions:
            accepted_captions.add(caption_index)
        caption = (
            table_captions[caption_index]
            if table_captions
            else f"Table {len(tables) + 1} (page {page_number})"
        )
        tables.append(
            ExtractedTable(
                page=page_number,
                caption=caption,
                rows=rows,
            )
        )

    for index, caption in enumerate(table_captions):
        if index not in accepted_captions:
            tables.append(
                ExtractedTable(
                    page=page_number,
                    caption=caption,
                    rows=[],
                    preview_only=True,
                )
            )

    return figures, tables, equations


def extract_table_preview(
    data: bytes,
    page_number: int,
    table_index: int,
) -> bytes:
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ParserError("Unable to open the PDF.") from exc

    try:
        if page_number < 1 or page_number > document.page_count:
            raise ParserError("The requested table page does not exist.")

        page = document[page_number - 1]
        _, tables, _ = _extract_page_assets(page, page_number)
        if table_index < 0 or table_index >= len(tables):
            raise ParserError("The requested table was not found.")

        caption = tables[table_index].caption
        label = " ".join(caption.split()[:2]).rstrip(".:")
        matches = page.search_for(label)
        if not matches:
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(1.5, 1.5),
                alpha=False,
            )
        else:
            caption_rect = matches[0]
            crop = fitz.Rect(
                page.rect.x0,
                max(page.rect.y0, caption_rect.y0 - 8),
                page.rect.x1,
                page.rect.y1,
            )
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(1.5, 1.5),
                clip=crop,
                alpha=False,
            )

        return pixmap.tobytes("png")
    finally:
        document.close()


def _has_vector_visual(page: fitz.Page) -> bool:
    drawings = page.get_drawings()
    if len(drawings) < 4:
        return False

    bounds = fitz.Rect()
    for drawing in drawings:
        bounds.include_rect(drawing["rect"])

    return bounds.get_area() >= page.rect.get_area() * 0.1


def extract_figure_image(
    data: bytes,
    page_number: int,
    xref: int,
) -> tuple[bytes, str]:
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ParserError("Unable to open the PDF.") from exc

    try:
        if page_number < 1 or page_number > document.page_count:
            raise ParserError("The requested figure page does not exist.")

        page = document[page_number - 1]
        if xref == 0:
            has_caption = any(
                _FIGURE_CAPTION_RE.match(line.strip())
                for line in page.get_text("text").splitlines()
            )
            if not has_caption and not _has_vector_visual(page):
                raise ParserError("The requested figure was not found.")
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(1.5, 1.5),
                alpha=False,
            )
            return pixmap.tobytes("png"), "image/png"

        if xref not in {
            image[0]
            for image in page.get_images(full=True)
            if image
        }:
            raise ParserError("The requested figure was not found.")

        extracted = document.extract_image(xref)
        mime_type = extracted.get("mime") or mimetypes.guess_type(
            f"figure.{extracted.get('ext', '')}"
        )[0] or "application/octet-stream"
        return extracted["image"], mime_type
    finally:
        document.close()


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
    figures: list[FigureAsset] = []
    tables: list[ExtractedTable] = []
    equations: list[ExtractedEquation] = []
    metadata: dict[str, str | None] = {}

    try:
        metadata = document.metadata or {}

        for index, page in enumerate(document):
            text = page.get_text("text")

            pages.append(
                PageText(
                    page=index + 1,
                    text=text,
                )
            )
            page_figures, page_tables, page_equations = (
                _extract_page_assets(page, index + 1)
            )
            figures.extend(page_figures)
            tables.extend(page_tables)
            equations.extend(page_equations)

        markdown = pymupdf4llm.to_markdown(
            document,
            show_progress=False,
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
        metadata=metadata,
        figures=figures,
        tables=tables,
        equations=equations,
    )