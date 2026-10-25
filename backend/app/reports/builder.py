from __future__ import annotations

from dataclasses import dataclass, field

from app.analysis.compare import (
    ComparisonResult,
)
from app.analysis.extract import (
    FindingsResult,
    LimitationsResult,
    MethodologyResult,
)
from app.analysis.summarize import (
    SummaryResult,
)


@dataclass
class ReportData:
    title: str
    summary: SummaryResult
    findings: FindingsResult
    methodology: MethodologyResult
    limitations: LimitationsResult
    comparison: ComparisonResult | None = None
    chart_paths: list[str] = field(
        default_factory=list
    )


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

    for finding in report.findings.findings:
        lines.extend(
            [
                (
                    f"- **{finding.finding}** "
                    f"(p. {finding.page}): "
                    f"{finding.evidence}"
                )
            ]
        )

    lines.extend(
        [
            "",
            "## Methodology",
            "",
            report.methodology.method,
            "",
            "### Models",
            "",
            _bullet_lines(
                report.methodology.models
            ),
            "",
            "### Datasets",
            "",
            _bullet_lines(
                report.methodology.datasets
            ),
            "",
            "### Metrics",
            "",
            _bullet_lines(
                report.methodology.metrics
            ),
            "",
            "### Experimental Setup",
            "",
            report.methodology.experimental_setup,
            "",
            "## Limitations",
            "",
        ]
    )

    for limitation in report.limitations.limitations:
        lines.append(
            (
                f"- {limitation.text} ({limitation.type})"
                if limitation.page <= 0
                else (
                    f"- {limitation.text} "
                    f"({limitation.type}, "
                    f"p. {limitation.page})"
                )
            )
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

    if report.chart_paths:
        lines.extend(
            [
                "",
                "## Visualizations",
                "",
            ]
        )

        for path in report.chart_paths:
            lines.append(
                f"![Visualization]({path})"
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