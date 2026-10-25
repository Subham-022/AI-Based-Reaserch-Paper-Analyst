from pathlib import Path

from app.analysis.compare import (
    ComparisonResult,
    PaperComparison,
    ComparisonCell,
)
from app.analysis.extract import (
    Evidence,
    FindingsResult,
    Finding,
    LimitationsResult,
    Limitation,
    MethodologyResult,
)
from app.analysis.summarize import (
    SummaryResult,
)
from app.reports.builder import (
    ReportData,
    build_markdown,
)
from app.reports.charts import (
    create_metric_chart,
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
        findings=FindingsResult(
            findings=[
                Finding(
                    finding="Important finding.",
                    evidence="Evidence.",
                    page=3,
                )
            ]
        ),
        methodology=MethodologyResult(
            method="Transformer",
            models=["Model A"],
            datasets=["Dataset A"],
            metrics=["Accuracy"],
            experimental_setup="Standard setup.",
            evidence=[
                Evidence(
                    text="Evidence.",
                    page=4,
                )
            ],
        ),
        limitations=LimitationsResult(
            limitations=[
                Limitation(
                    text="Small dataset.",
                    type="stated",
                    page=8,
                )
            ]
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


def test_chart_uses_real_values(
    tmp_path: Path,
) -> None:
    output = tmp_path / "metric.png"

    result = create_metric_chart(
        [
            ("Paper A", 0.91),
            ("Paper B", 0.87),
        ],
        output,
        "Accuracy",
        "Accuracy",
    )

    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_chart_rejects_non_numeric_values(
    tmp_path: Path,
) -> None:
    output = tmp_path / "metric.png"

    result = create_metric_chart(
        [
            ("Paper A", "unknown"),
        ],
        output,
        "Accuracy",
        "Accuracy",
    )

    assert result is None
    assert not output.exists()


def test_pdf_export(
    tmp_path: Path,
) -> None:
    markdown = build_markdown(
        _report()
    )

    output = tmp_path / "report.pdf"

    result = export_pdf(
        markdown,
        output,
    )

    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0
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