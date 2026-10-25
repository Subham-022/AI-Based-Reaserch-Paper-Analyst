from __future__ import annotations

import json
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
from app.models import Paper, Report


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


def _get_llm():
    from app.config import (
        LLM_API_KEY,
        LLM_BASE_URL,
        LLM_MODEL,
        LLM_PROVIDER,
        OLLAMA_BASE_URL,
    )

    if LLM_PROVIDER == "ollama":
        from app.llm.ollama_client import (
            OllamaClient,
        )

        return OllamaClient(
            base_url=OLLAMA_BASE_URL,
            model=LLM_MODEL,
        )

    from app.llm.anthropic_client import (
        AnthropicClient,
    )

    return AnthropicClient(
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
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

    try:
        from app.analysis.extract import (
            extract_findings,
            analyze_methodology,
            extract_limitations,
        )
        from app.analysis.summarize import (
            SummaryResult,
        )
        from app.reports.builder import (
            ReportData,
            build_markdown,
        )

        llm = _get_llm()

        primary = papers[0]

        if not primary.summary_json:
            raise RuntimeError(
                "Paper summary is unavailable."
            )

        summary = SummaryResult.model_validate_json(
            primary.summary_json
        )

        from app.retrieval.search import search

        citations = search(
            query="important findings methodology limitations",
            paper_ids=[
                paper.id
                for paper in papers
            ],
        )

        content = "\n\n".join(
            item.text
            for item in citations
        )

        findings = extract_findings(
            llm,
            content,
        )

        methodology = analyze_methodology(
            llm,
            content,
        )

        limitations = extract_limitations(
            llm,
            content,
        )

        report_data = ReportData(
            title=(
                "Research Paper Analysis"
                if len(papers) > 1
                else (
                    primary.title
                    or "Research Paper Analysis"
                )
            ),
            summary=summary,
            findings=findings,
            methodology=methodology,
            limitations=limitations,
        )

        markdown = build_markdown(
            report_data
        )

        report_id = uuid.uuid4().hex

        markdown_path = (
            REPORT_DIR
            / f"{report_id}.md"
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

            pdf_path = (
                REPORT_DIR
                / f"{report_id}.pdf"
            )

            export_pdf(
                markdown,
                pdf_path,
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