from pathlib import Path

import pytest

from app.ingestion.loader import (
    LoaderError,
    load_file,
)


def test_loader_rejects_missing_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "missing.pdf"

    with pytest.raises(
        LoaderError,
        match="does not exist",
    ):
        load_file(path)


def test_loader_rejects_non_pdf(
    tmp_path: Path,
) -> None:
    path = tmp_path / "document.txt"

    path.write_text(
        "This is not a PDF.",
        encoding="utf-8",
    )

    with pytest.raises(
        LoaderError,
        match="Only PDF",
    ):
        load_file(path)


def test_loader_rejects_invalid_pdf(
    tmp_path: Path,
) -> None:
    path = tmp_path / "document.pdf"

    path.write_bytes(
        b"This is not really a PDF."
    )

    with pytest.raises(
        LoaderError,
        match="valid PDF",
    ):
        load_file(path)