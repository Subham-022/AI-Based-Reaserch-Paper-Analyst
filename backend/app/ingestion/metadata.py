from __future__ import annotations

import re
from dataclasses import dataclass


_DOI_RE = re.compile(
    r"""
    10\.\d{4,9}/
    [-._;()/:A-Z0-9]+
    """,
    re.IGNORECASE | re.VERBOSE,
)


_ARXIV_RE = re.compile(
    r"""
    (?:arXiv:\s*)?
    (
        \d{4}\.\d{4,5}
        (?:v\d+)?
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


_YEAR_RE = re.compile(
    r"\b(?:19|20)\d{2}\b"
)


@dataclass(frozen=True)
class PaperMetadata:
    title: str | None
    authors: list[str]
    venue: str | None
    year: int | None
    doi: str | None
    arxiv_id: str | None


def _find_title(
    lines: list[str],
) -> str | None:
    for line in lines[:20]:
        if not 12 <= len(line) <= 240:
            continue

        if _YEAR_RE.fullmatch(line):
            continue

        if _DOI_RE.fullmatch(line):
            continue

        if line.lower().startswith(
            ("doi:", "arxiv:")
        ):
            continue

        return line

    return None


def _find_authors(
    lines: list[str],
    title: str | None,
) -> list[str]:
    if not title or title not in lines:
        return []

    title_index = lines.index(title)

    candidates = lines[
        title_index + 1 : title_index + 5
    ]

    for line in candidates:
        if "," not in line and (
            " and " not in line.lower()
        ):
            continue

        authors = [
            item.strip()
            for item in re.split(
                r",|\band\b",
                line,
                flags=re.IGNORECASE,
            )
            if item.strip()
        ]

        if len(authors) >= 2:
            return authors

    return []


def _find_venue(
    lines: list[str],
) -> str | None:
    markers = (
        "journal",
        "conference",
        "proceedings",
        "transactions",
    )

    for line in lines:
        lower = line.lower()

        if any(
            marker in lower
            for marker in markers
        ):
            return line

    return None


def extract_metadata(
    pages: list[str],
    source_url: str | None = None,
    pdf_metadata: dict[str, str | None] | None = None,
    fallback_title: str | None = None,
) -> PaperMetadata:
    first_pages = "\n".join(
        pages[:2]
    )

    lines = [
        line.strip()
        for line in first_pages.splitlines()
        if line.strip()
    ]

    embedded_title = ((pdf_metadata or {}).get("title") or "").strip()
    text_title = _find_title(lines)
    title = embedded_title or text_title or fallback_title
    authors = _find_authors(
        lines,
        text_title,
    )
    if not authors:
        embedded_authors = (
            (pdf_metadata or {}).get("author") or ""
        ).strip()
        authors = [
            author.strip()
            for author in re.split(
                r";|\band\b",
                embedded_authors,
                flags=re.IGNORECASE,
            )
            if author.strip()
        ]
    venue = _find_venue(lines)

    doi_match = _DOI_RE.search(
        first_pages
    )

    arxiv_match = _ARXIV_RE.search(
        source_url or ""
    )

    if not arxiv_match:
        arxiv_match = _ARXIV_RE.search(
            first_pages
        )

    year_match = _YEAR_RE.search(
        first_pages
    )

    doi = None

    if doi_match:
        doi = doi_match.group(0).rstrip(
            ".,;)"
        )

    arxiv_id = None

    if arxiv_match:
        arxiv_id = arxiv_match.group(1)

    year = None

    if year_match:
        year = int(
            year_match.group(0)
        )

    return PaperMetadata(
        title=title,
        authors=authors,
        venue=venue,
        year=year,
        doi=doi,
        arxiv_id=arxiv_id,
    )