from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


_HEADING_RE = re.compile(
    r"""
    ^\s*
    (?:
        \d+(?:\.\d+)*[.)]?\s+
    )?
    (?P<name>
        abstract|
        introduction|
        related\s+work|
        background|
        methods?|
        methodology|
        experiments?|
        results?|
        discussion|
        conclusions?|
        limitations?|
        references
    )
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class Section:
    name: str
    text: str
    start_page: int
    end_page: int
    page_parts: tuple[
        tuple[int, str],
        ...
    ] = ()


@dataclass(frozen=True)
class Chunk:
    id: str
    paper_id: str
    section: str
    page: int
    text: str
    content_type: str
    content_hash: str


def _canonical_section_name(
    name: str,
) -> str:
    value = re.sub(
        r"\s+",
        " ",
        name.lower(),
    ).strip()

    aliases = {
        "method": "methods",
        "experiment": "experiments",
        "result": "results",
        "conclusion": "conclusion",
        "reference": "references",
    }

    return aliases.get(
        value,
        value,
    )


def detect_sections(
    pages: list[tuple[int, str]],
) -> list[Section]:
    sections: list[Section] = []

    current_name = "front matter"

    current_parts: list[
        tuple[int, str]
    ] = []

    def flush_section() -> None:
        nonlocal current_parts

        if not current_parts:
            return

        combined_text = "\n".join(
            text
            for _, text in current_parts
        )

        sections.append(
            Section(
                name=current_name,
                text=combined_text,
                start_page=current_parts[0][0],
                end_page=current_parts[-1][0],
                page_parts=tuple(
                    current_parts
                ),
            )
        )

        current_parts = []

    for page_number, page_text in pages:
        lines = page_text.splitlines()
        normal_lines: list[str] = []

        for line in lines:
            match = _HEADING_RE.match(line)

            if match:
                if normal_lines:
                    text = "\n".join(
                        normal_lines
                    ).strip()

                    if text:
                        current_parts.append(
                            (
                                page_number,
                                text,
                            )
                        )

                    normal_lines = []

                flush_section()

                current_name = (
                    _canonical_section_name(
                        match.group("name")
                    )
                )

                continue

            normal_lines.append(line)

        if normal_lines:
            text = "\n".join(
                normal_lines
            ).strip()

            if text:
                current_parts.append(
                    (
                        page_number,
                        text,
                    )
                )

    flush_section()

    return sections


def _detect_content_type(
    block: str,
) -> str:
    lower = block.lower().strip()

    if (
        lower.startswith("table")
        or lower.startswith("table.")
        or " | " in block
    ):
        return "table"

    if (
        lower.startswith("figure")
        or lower.startswith("fig.")
        or lower.startswith("figure.")
    ):
        return "figure_caption"

    return "text"


def _split_blocks(
    text: str,
) -> list[tuple[str, str]]:
    raw_blocks = re.split(
        r"\n\s*\n",
        text,
    )

    blocks: list[
        tuple[str, str]
    ] = []

    for raw_block in raw_blocks:
        block = raw_block.strip()

        if not block:
            continue

        content_type = _detect_content_type(
            block
        )

        blocks.append(
            (
                content_type,
                block,
            )
        )

    return blocks


def _make_text_chunks(
    words: list[str],
    target_words: int,
    overlap_words: int,
) -> list[list[str]]:
    if len(words) <= target_words:
        return [words]

    chunks: list[list[str]] = []

    step = max(
        1,
        target_words - overlap_words,
    )

    for start in range(
        0,
        len(words),
        step,
    ):
        chunk_words = words[
            start : start + target_words
        ]

        if not chunk_words:
            break

        chunks.append(chunk_words)

        if (
            start + target_words
            >= len(words)
        ):
            break

    return chunks


def chunk_sections(
    paper_id: str,
    sections: list[Section],
    target_words: int = 675,
    overlap_words: int = 90,
) -> list[Chunk]:
    chunks: list[Chunk] = []

    sequence = 0

    for section in sections:
        page_parts = section.page_parts

        if not page_parts:
            page_parts = (
                (
                    section.start_page,
                    section.text,
                ),
            )

        for page_number, page_text in page_parts:
            blocks = _split_blocks(
                page_text
            )

            for content_type, block in blocks:
                words = block.split()

                if content_type in {
                    "table",
                    "figure_caption",
                }:
                    word_groups = [words]
                else:
                    word_groups = _make_text_chunks(
                        words,
                        target_words,
                        overlap_words,
                    )

                for group in word_groups:
                    text = " ".join(
                        group
                    ).strip()

                    if not text:
                        continue

                    sequence += 1

                    content_hash = hashlib.sha256(
                        text.encode("utf-8")
                    ).hexdigest()

                    chunks.append(
                        Chunk(
                            id=(
                                f"{paper_id}:"
                                f"{sequence}"
                            ),
                            paper_id=paper_id,
                            section=section.name,
                            page=page_number,
                            text=text,
                            content_type=content_type,
                            content_hash=content_hash,
                        )
                    )

    return chunks
