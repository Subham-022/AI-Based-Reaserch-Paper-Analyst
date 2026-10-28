from __future__ import annotations

from dataclasses import dataclass

from app.analysis.compare import (
    ComparisonResult,
)
from app.analysis.summarize import (
    SummaryResult,
)


@dataclass
class ReportData:
    title: str
    summary: SummaryResult
    comparison: ComparisonResult | None = None


def _bullet_lines(
    values: list[str],
) -> str:
    if not values:
        return "- None reported"

    return "\n".join(
        f"- {value}"
        for value in values
    )


def build_markdown(
    report: ReportData,
) -> str:
    lines = [
        f"# {report.title}",
        "",
        "## Executive Summary",
        "",
        report.summary.summary,
        "",
        "## Research Problem",
        "",
        report.summary.problem,
        "",
        "## Approach",
        "",
        report.summary.approach,
        "",
        "## Main Result",
        "",
        report.summary.main_result,
        "",
        "## Key Findings",
        "",
    ]

    lines.append(_bullet_lines(report.summary.key_findings))

    lines.extend(
        [
            "",
            "## Methodology",
            "",
            report.summary.approach,
            "",
            "### Methodology Details",
            "",
            _bullet_lines(report.summary.methodology_details),
            "",
            "### Datasets",
            "",
            _bullet_lines(report.summary.datasets),
            "",
            "### Metrics",
            "",
            _bullet_lines(report.summary.evaluation_metrics),
        ]
    )

    if report.summary.quantitative_results:
        lines.extend(
            [
                "",
                "### Quantitative Results",
                "",
                _bullet_lines(report.summary.quantitative_results),
            ]
        )

    if report.summary.equations_and_calculations:
        lines.extend(
            [
                "",
                "### Equations and Calculations",
                "",
                _bullet_lines(report.summary.equations_and_calculations),
            ]
        )

    if report.summary.analysis_of_visuals_and_tables:
        lines.extend(
            [
                "",
                "### Analysis of Figures and Tables",
                "",
                _bullet_lines(report.summary.analysis_of_visuals_and_tables),
            ]
        )

    lines.extend(
        [
            "",
            "## Limitations",
            "",
            _bullet_lines(report.summary.limitations),
        ]
    )

    if report.comparison:
        lines.extend(
            [
                "",
                "## Comparison",
                "",
                _comparison_table(
                    report.comparison
                ),
            ]
        )

    return "\n".join(lines).strip() + "\n"


def _comparison_table(
    comparison: ComparisonResult,
) -> str:
    headers = [
        "Paper",
        "Problem",
        "Method",
        "Dataset",
        "Metrics",
        "Results",
        "Limitations",
    ]

    rows = [
        "| "
        + " | ".join(headers)
        + " |",
        "| "
        + " | ".join(
            "---"
            for _ in headers
        )
        + " |",
    ]

    for paper in comparison.papers:
        values = [
            paper.paper_id,
            paper.problem.value,
            paper.method.value,
            paper.dataset.value,
            paper.metrics.value,
            paper.results.value,
            paper.limitations.value,
        ]

        values = [
            value.replace(
                "|",
                "\\|",
            )
            for value in values
        ]

        rows.append(
            "| "
            + " | ".join(values)
            + " |"
        )

    return "\n".join(rows)