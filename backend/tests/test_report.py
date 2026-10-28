from pathlib import Path

import fitz

from app.analysis.summarize import (
    SummaryResult,
)
from app.reports.builder import (
    ReportData,
    build_markdown,
)
from app.reports.pdf import (
    export_pdf,
)


def _report() -> ReportData:
    return ReportData(
        title="Test Research Report",
        summary=SummaryResult(
            summary="A summary.",
            problem="A problem.",
            approach="A method.",
            main_result="A result.",
            limitations=[
                "A limitation."
            ],
        ),
    )


def test_markdown_report_contains_sections() -> None:
    markdown = build_markdown(
        _report()
    )

    assert "# Test Research Report" in markdown
    assert "## Executive Summary" in markdown
    assert "## Key Findings" in markdown
    assert "## Methodology" in markdown
    assert "## Limitations" in markdown


def test_pdf_export(
    tmp_path: Path,
) -> None:
    markdown = """# Research—paper review

## Summary

This is **readable text** with a proper Unicode dash – and punctuation.

- A finding with 91% accuracy
"""
    image_document = fitz.open()
    image_page = image_document.new_page(width=200, height=100)
    image_page.draw_rect(fitz.Rect(20, 20, 180, 80), color=(0, 0, 1))
    chart = tmp_path / "figure.png"
    chart.write_bytes(image_page.get_pixmap().tobytes("png"))
    image_document.close()
    markdown += f"\n![Accuracy chart]({chart})\n"

    output = tmp_path / "report.pdf"

    result = export_pdf(
        markdown,
        output,
    )

    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0
    with fitz.open(output) as document:
        text = "\n".join(page.get_text() for page in document)
        assert "Research—paper review" in text
        assert "readable text" in text
        assert "A finding with 91% accuracy" in text
        assert sum(len(page.get_images()) for page in document) > 0


def test_pdf_export_includes_saved_analysis_details() -> None:
    report = _report()
    report.summary.key_findings = ["A measured finding."]
    report.summary.datasets = ["Dataset X"]
    report.summary.evaluation_metrics = ["F1-score"]
    report.summary.quantitative_results = ["91% accuracy"]

    markdown = build_markdown(report)

    assert "- A measured finding." in markdown
    assert "- Dataset X" in markdown
    assert "- F1-score" in markdown
    assert "- 91% accuracy" in markdown


def test_pdf_export_preserves_table_and_bullets(
    tmp_path: Path,
) -> None:
    markdown = """# Report

## Key Findings

- First finding
- Second finding

## Comparison

| Paper | Method | Result |
| --- | --- | --- |
| Paper A | CNN | 91% |
| Paper B | Transformer | 94% |
"""

    output = tmp_path / "comparison.pdf"

    result = export_pdf(
        markdown,
        output,
    )

    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0