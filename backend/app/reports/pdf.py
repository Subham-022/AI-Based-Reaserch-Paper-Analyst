from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


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
                    _escape(cell),
                    getSampleStyleSheet()["BodyText"],
                )
                for cell in row
            ]
            for row in rows
        ],
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
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    styles = getSampleStyleSheet()

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=42,
        leftMargin=42,
        topMargin=42,
        bottomMargin=42,
    )

    story = []

    for kind, value in _markdown_to_blocks(markdown):
        if kind == "title":
            story.append(
                Paragraph(
                    _escape(value),
                    styles["Title"],
                )
            )
            story.append(Spacer(1, 12))

        elif kind == "heading2":
            story.append(
                Paragraph(
                    _escape(value),
                    styles["Heading2"],
                )
            )
            story.append(Spacer(1, 6))

        elif kind == "heading3":
            story.append(
                Paragraph(
                    _escape(value),
                    styles["Heading3"],
                )
            )

        elif kind == "bullet":
            story.append(
                Paragraph(
                    "• " + _escape(value),
                    styles["BodyText"],
                )
            )
            story.append(Spacer(1, 4))

        elif kind == "table":
            story.append(_table_flowable(value))
            story.append(Spacer(1, 12))

        elif kind == "image":
            image_path = Path(value)

            if image_path.exists():
                image = Image(str(image_path))
                image._restrictSize(
                    170 * mm,
                    100 * mm,
                )
                story.append(image)
                story.append(Spacer(1, 12))

        else:
            story.append(
                Paragraph(
                    _escape(value),
                    styles["BodyText"],
                )
            )
            story.append(Spacer(1, 6))

    document.build(story)

    return output_path