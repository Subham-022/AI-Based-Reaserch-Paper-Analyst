from __future__ import annotations

import re
from collections import Counter


_WHITESPACE_RE = re.compile(
    r"[ \t]+"
)

_PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:page\s+)?\d+\s*$",
    re.IGNORECASE,
)


def _normalise_line(line: str) -> str:
    return _WHITESPACE_RE.sub(
        " ",
        line,
    ).strip()


def _find_repeated_lines(
    pages: list[str],
) -> set[str]:
    counts: Counter[str] = Counter()

    for page in pages:
        page_lines: set[str] = set()

        for raw_line in page.splitlines():
            line = _normalise_line(raw_line)

            if not line:
                continue

            if len(line) > 160:
                continue

            page_lines.add(line)

        counts.update(page_lines)

    minimum_occurrences = max(
        2,
        len(pages) // 3,
    )

    return {
        line
        for line, count in counts.items()
        if count >= minimum_occurrences
    }


def clean_pages(
    pages: list[str],
) -> list[str]:
    if not pages:
        return []

    repeated_lines = _find_repeated_lines(
        pages
    )

    cleaned_pages: list[str] = []

    for page in pages:
        output_lines: list[str] = []

        for raw_line in page.splitlines():
            line = _normalise_line(raw_line)

            if not line:
                continue

            if _PAGE_NUMBER_RE.fullmatch(line):
                continue

            if line in repeated_lines:
                continue

            output_lines.append(line)

        cleaned_pages.append(
            "\n".join(output_lines)
        )

    return cleaned_pages


def clean_text(
    text: str,
) -> str:
    if not text:
        return ""

    cleaned_pages = clean_pages(
        text.split("\f")
    )

    return "\n\n".join(
        page
        for page in cleaned_pages
        if page.strip()
    )