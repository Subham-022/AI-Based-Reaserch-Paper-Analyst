from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.models import Paper


router = APIRouter(
    tags=["comparison"],
)


class CompareRequest(BaseModel):
    paper_ids: list[str]


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


@router.post("/compare")
def compare_papers(
    request: CompareRequest,
    session: Session = Depends(
        get_session
    ),
) -> dict:
    if len(
        set(request.paper_ids)
    ) < 2:
        raise _error(
            400,
            "TOO_FEW_PAPERS",
            "Select at least two different papers.",
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
        from app.retrieval.search import search

        evidence: dict[str, str] = {}

        dimensions = [
            "problem",
            "method",
            "dataset",
            "metrics",
            "results",
            "limitations",
        ]

        for paper in papers:
            passages: list[str] = []

            for dimension in dimensions:
                citations = search(
                    query=dimension,
                    paper_ids=[paper.id],
                )

                passages.extend(
                    item.text
                    for item in citations[:3]
                )

            evidence[paper.id] = "\n\n".join(
                dict.fromkeys(passages)
            )

        llm = _get_llm()

        from app.analysis.compare import (
            compare_papers as run_comparison,
        )

        result = run_comparison(
            llm,
            evidence,
        )

        return {
            "papers": [
                {
                    "id": paper.id,
                    "title": paper.title
                    or paper.original_filename,
                }
                for paper in papers
            ],
            "rows": _comparison_rows(
                result
            ),
            "charts": [],
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise _error(
            502,
            "ANALYSIS_FAILED",
            "The papers could not be compared.",
        ) from exc


def _comparison_rows(
    result,
) -> list[dict]:
    dimensions = [
        "problem",
        "method",
        "dataset",
        "metrics",
        "results",
        "limitations",
    ]

    rows = []

    for dimension in dimensions:
        cells = []

        for paper in result.papers:
            cell = getattr(
                paper,
                dimension,
            )

            cells.append(
                {
                    "paper_id": paper.paper_id,
                    "value": cell.value,
                    "citations": [
                        citation.model_dump()
                        for citation
                        in cell.citations
                    ],
                }
            )

        rows.append(
            {
                "dimension": dimension,
                "cells": cells,
            }
        )

    return rows