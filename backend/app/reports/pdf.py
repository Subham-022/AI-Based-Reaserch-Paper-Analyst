from __future__ import annotations

import re
from pathlib import Path

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _register_fonts() -> None:
    if "ReportBody" in pdfmetrics.getRegisteredFontNames():
        return

    font_dir = Path(reportlab.__file__).parent / "fonts"
    pdfmetrics.registerFont(TTFont("ReportBody", str(font_dir / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("ReportBold", str(font_dir / "VeraBd.ttf")))
    pdfmetrics.registerFont(TTFont("ReportItalic", str(font_dir / "VeraIt.ttf")))
    pdfmetrics.registerFont(TTFont("ReportBoldItalic", str(font_dir / "VeraBI.ttf")))
    pdfmetrics.registerFontFamily(
        "ReportBody",
        normal="ReportBody",
        bold="ReportBold",
        italic="ReportItalic",
        boldItalic="ReportBoldItalic",
    )


def _inline_markup(text: str) -> str:
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    return re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", escaped)


def _parse_table_row(line: str) -> list[str]:
    cells = line.strip().strip("|").split("|")
    return [cell.strip() for cell in cells]


def _is_table_separator(line: str) -> bool:
    cells = _parse_table_row(line)
    return bool(cells) and all(
        re.fullmatch(r":?-+:?", cell) for cell in cells
    )


def _markdown_to_blocks(
    markdown: str,
) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    lines = markdown.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index].strip()

        if not line:
            index += 1
            continue

        if line.startswith("### "):
            blocks.append(("heading3", line[4:]))
            index += 1
            continue

        if line.startswith("## "):
            blocks.append(("heading2", line[3:]))
            index += 1
            continue

        if line.startswith("# "):
            blocks.append(("title", line[2:]))
            index += 1
            continue

        if line.startswith("- "):
            blocks.append(("bullet", line[2:]))
            index += 1
            continue

        if line.startswith("!["):
            match = re.search(r"\]\((.*?)\)", line)

            if match:
                blocks.append(("image", match.group(1)))

            index += 1
            continue

        if line.startswith("|"):
            table_lines = []

            while index < len(lines):
                table_line = lines[index].strip()

                if not table_line.startswith("|"):
                    break

                table_lines.append(table_line)
                index += 1

            if len(table_lines) >= 2:
                blocks.append(
                    ("table", "\n".join(table_lines))
                )

            continue

        blocks.append(("body", line))
        index += 1

    return blocks


def _table_flowable(
    value: str,
    styles,
    available_width: float,
) -> Table:
    rows = [
        _parse_table_row(line)
        for line in value.splitlines()
        if line.strip()
    ]

    if len(rows) >= 2 and _is_table_separator(
        value.splitlines()[1]
    ):
        rows.pop(1)

    table = Table(
        [
            [
                Paragraph(
                    _inline_markup(cell),
                    styles["ReportCell"],
                )
                for cell in row
            ]
            for row in rows
        ],
        colWidths=[available_width / max(len(row) for row in rows)] * max(
            len(row) for row in rows
        ),
        repeatRows=1,
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    return table


def export_pdf(
    markdown: str,
    output_path: Path,
) -> Path:
    _register_fonts()
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "ReportBody"
    styles["Normal"].leading = 15
    styles["BodyText"].fontName = "ReportBody"
    styles["BodyText"].leading = 15
    styles["BodyText"].spaceAfter = 6
    styles["Title"].fontName = "ReportBold"
    styles["Heading1"].fontName = "ReportBold"
    styles["Heading2"].fontName = "ReportBold"
    styles["Heading3"].fontName = "ReportBold"
    styles.add(
        ParagraphStyle(
            "ReportCell",
            parent=styles["BodyText"],
            fontSize=8,
            leading=10,
            spaceAfter=0,
        )
    )

    page_width, _ = A4
    margin = 42
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=margin,
        leftMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )

    story = []

    for kind, value in _markdown_to_blocks(markdown):
        if kind == "title":
            story.append(
                Paragraph(
                    _inline_markup(value),
                    styles["Title"],
                )
            )
            story.append(Spacer(1, 12))

        elif kind == "heading2":
            story.append(
                Paragraph(
                    _inline_markup(value),
                    styles["Heading2"],
                )
            )
            story.append(Spacer(1, 6))

        elif kind == "heading3":
            story.append(
                Paragraph(
                    _inline_markup(value),
                    styles["Heading3"],
                )
            )

        elif kind == "bullet":
            story.append(
                Paragraph(
                    "• " + _inline_markup(value),
                    styles["BodyText"],
                )
            )
            story.append(Spacer(1, 4))

        elif kind == "table":
            story.append(
                _table_flowable(
                    value,
                    styles,
                    page_width - 2 * margin,
                )
            )
            story.append(Spacer(1, 12))

        elif kind == "image":
            image_path = Path(value)
            if not image_path.is_file():
                raise FileNotFoundError(
                    f"Report image does not exist: {image_path}"
                )
            image = Image(str(image_path))
            image._restrictSize(165 * mm, 100 * mm)
            story.append(image)
            story.append(Spacer(1, 12))

        else:
            story.append(
                Paragraph(
                    _inline_markup(value),
                    styles["BodyText"],
                )
            )
            story.append(Spacer(1, 6))

    document.build(story)

    return output_path