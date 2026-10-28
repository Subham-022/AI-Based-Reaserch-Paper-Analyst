from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.config import REPORT_DIR
from app.db import get_session
from app.ingestion.loader import load_file
from app.models import Paper, Report
from app.ingestion.parser import (
    extract_figure_image,
    extract_table_preview,
    parse_pdf,
)

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/reports",
    tags=["reports"],
)


class ReportRequest(BaseModel):
    paper_ids: list[str]
    format: str = "pdf"


def _error(
    status_code: int,
    code: str,
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
            }
        },
    )


def _append_pdf_assets(
    markdown: str,
    papers: list[Paper],
    report_id: str,
    generated_paths: list[Path],
) -> str:
    sections: list[str] = []

    for paper_index, paper in enumerate(papers):
        pdf_data = load_file(Path(paper.storage_path))
        parsed = parse_pdf(pdf_data)
        if not parsed.figures and not parsed.tables:
            continue

        title = paper.title or Path(paper.original_filename).stem
        if len(papers) > 1:
            sections.extend(["### " + title, ""])

        for figure_index, figure in enumerate(parsed.figures):
            image_data, media_type = extract_figure_image(
                pdf_data,
                figure.page,
                figure.xref,
            )
            extension = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
            }.get(media_type)
            if extension is None:
                import fitz

                image_data = fitz.Pixmap(image_data).tobytes("png")
                extension = ".png"

            image_path = REPORT_DIR / (
                f"{report_id}-paper-{paper_index}-figure-{figure_index}{extension}"
            )
            generated_paths.append(image_path)
            image_path.write_bytes(image_data)
            sections.extend(
                [
                    f"#### Figure, page {figure.page}: {figure.caption}",
                    "",
                    f"![{figure.caption}]({image_path})",
                    "",
                ]
            )

        for table_index, table in enumerate(parsed.tables):
            image_data = extract_table_preview(
                pdf_data,
                table.page,
                sum(
                    1
                    for previous in parsed.tables[:table_index]
                    if previous.page == table.page
                ),
            )
            image_path = REPORT_DIR / (
                f"{report_id}-paper-{paper_index}-table-{table_index}.png"
            )
            generated_paths.append(image_path)
            image_path.write_bytes(image_data)
            sections.extend(
                [
                    f"#### Table, page {table.page}: {table.caption}",
                    "",
                    f"![{table.caption}]({image_path})",
                    "",
                ]
            )

    if not sections:
        return markdown

    return (
        markdown.rstrip()
        + "\n\n## Figures and Tables\n\n"
        + "\n".join(sections)
    )


@router.post("")
def create_report(
    request: ReportRequest,
    session: Session = Depends(
        get_session
    ),
) -> dict:
    if request.format not in {
        "md",
        "pdf",
    }:
        raise _error(
            400,
            "INVALID_FORMAT",
            "Report format must be md or pdf.",
        )

    if not request.paper_ids:
        raise _error(
            400,
            "INVALID_PAPERS",
            "At least one paper is required.",
        )

    papers: list[Paper] = []

    for paper_id in request.paper_ids:
        paper = session.get(
            Paper,
            paper_id,
        )

        if paper is None:
            raise _error(
                404,
                "PAPER_NOT_FOUND",
                f"Paper {paper_id} does not exist.",
            )

        if paper.status != "ready":
            raise _error(
                409,
                "PAPER_NOT_READY",
                f"Paper {paper_id} is not ready.",
            )

        papers.append(paper)

    generated_paths: list[Path] = []

    try:
        from app.analysis.compare import (
            ComparisonCell,
            ComparisonResult,
            PaperComparison,
            SourceCitation,
        )
        from app.analysis.summarize import (
            SummaryResult,
        )
        from app.reports.builder import (
            ReportData,
            build_markdown,
        )

        primary = papers[0]

        if not primary.summary_json:
            raise RuntimeError(
                "Paper summary is unavailable."
            )

        summary = SummaryResult.model_validate_json(
            primary.summary_json
        )

        comparison = None
        if len(papers) > 1:
            from app.api.compare import (
                CompareRequest,
                compare_papers,
            )

            comparison_response = compare_papers(
                CompareRequest(
                    paper_ids=[
                        paper.id
                        for paper in papers
                    ]
                ),
                session,
            )
            comparison_rows = {
                row["dimension"]: row["cells"]
                for row in comparison_response["rows"]
            }
            comparison_papers = []

            for paper in papers:
                cells = {
                    dimension: next(
                        (
                            cell
                            for cell in comparison_rows[dimension]
                            if cell["paper_id"] == paper.id
                        ),
                        {
                            "value": "Not reported in retrieved evidence.",
                            "citations": [],
                        },
                    )
                    for dimension in (
                        "problem",
                        "method",
                        "dataset",
                        "metrics",
                        "results",
                        "limitations",
                    )
                }

                comparison_papers.append(
                    PaperComparison(
                        paper_id=paper.title
                        or paper.original_filename,
                        **{
                            dimension: ComparisonCell(
                                value=cell["value"],
                                citations=[
                                    SourceCitation(
                                        **citation
                                    )
                                    for citation in cell["citations"]
                                ],
                            )
                            for dimension, cell in cells.items()
                        },
                    )
                )

            comparison = ComparisonResult(
                papers=comparison_papers
            )

        report_data = ReportData(
            title=(
                "Research Paper Analysis"
                if len(papers) > 1
                else (
                    primary.title
                    or Path(
                        primary.original_filename
                    ).stem
                    or "Research Paper Analysis"
                )
            ),
            summary=summary,
            comparison=comparison,
        )

        markdown = build_markdown(
            report_data
        )

        report_id = uuid.uuid4().hex

        markdown_path = (
            REPORT_DIR
            / f"{report_id}.md"
        )
        generated_paths.append(
            markdown_path
        )

        markdown_path.write_text(
            markdown,
            encoding="utf-8",
        )

        final_path = markdown_path

        if request.format == "pdf":
            from app.reports.pdf import (
                export_pdf,
            )

            markdown = _append_pdf_assets(
                markdown,
                papers,
                report_id,
                generated_paths,
            )
            pdf_path = (
                REPORT_DIR
                / f"{report_id}.pdf"
            )
            generated_paths.append(
                pdf_path
            )

            export_pdf(
                markdown,
                pdf_path,
            )
            for path in generated_paths:
                if path not in {markdown_path, pdf_path}:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        logger.exception(
                            "Failed to remove report image %s",
                            path,
                        )

            final_path = pdf_path

        report = Report(
            id=report_id,
            title=report_data.title,
            format=request.format,
            storage_path=str(
                final_path
            ),
            paper_ids_json=json.dumps(
                request.paper_ids
            ),
        )

        session.add(report)
        session.commit()

        return {
            "report_id": report_id,
            "format": request.format,
            "download_url": (
                f"/api/reports/"
                f"{report_id}/download"
            ),
        }

    except HTTPException:
        raise

    except Exception as exc:
        session.rollback()
        for path in generated_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.exception(
                    "Failed to remove incomplete report file %s",
                    path,
                )
        logger.exception("Research report generation failed")
        raise _error(
            502,
            "REPORT_FAILED",
            "The report could not be generated.",
        ) from exc


@router.get("")
def list_reports(
    session: Session = Depends(
        get_session
    ),
) -> dict:
    reports = session.exec(
        select(Report).order_by(
            Report.created_at.desc()
        )
    ).all()

    return {
        "items": [
            {
                "id": report.id,
                "title": report.title,
                "format": report.format,
                "created_at": report.created_at,
            }
            for report in reports
        ]
    }


@router.get(
    "/{report_id}/download"
)
def download_report(
    report_id: str,
    session: Session = Depends(
        get_session
    ),
):
    report = session.get(
        Report,
        report_id,
    )

    if report is None:
        raise _error(
            404,
            "REPORT_NOT_FOUND",
            "The requested report does not exist.",
        )

    path = Path(
        report.storage_path
    )

    if not path.exists():
        raise _error(
            410,
            "REPORT_FILE_MISSING",
            "The generated report file is no longer available.",
        )

    media_type = (
        "application/pdf"
        if report.format == "pdf"
        else "text/markdown"
    )

    return FileResponse(
        path,
        media_type=media_type,
        filename=(
            f"research-paper-report."
            f"{report.format}"
        ),
    )