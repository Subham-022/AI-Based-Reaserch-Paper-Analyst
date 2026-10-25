from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.models import Paper
from app.retrieval.search import Citation

logger = logging.getLogger(__name__)

DIMENSION_EVIDENCE_PATTERNS = {
    "problem": re.compile(
        r"\b(problem|objective|aim|challenge|motivation|research question)\b",
        re.IGNORECASE,
    ),
    "method": re.compile(
        r"\b(method(?:ology)?|approach|algorithm|model|architecture|framework|network|proposed)\b",
        re.IGNORECASE,
    ),
    "dataset": re.compile(
        r"\b(dataset|data set|corpus|benchmark|training set|test set|validation set|participants|subjects|samples|records|ISIC|HAM10000)\b",
        re.IGNORECASE,
    ),
    "metrics": re.compile(
        r"\b(accuracy|precision|recall|F1(?:-score)?|AUC|ROC|specificity|sensitivity|BLEU|ROUGE|perplexity|RMSE|MAE|IoU)\b",
        re.IGNORECASE,
    ),
    "results": re.compile(
        r"\b(results?|findings?|achieved|performance|outperformed|improved|improvement)\b",
        re.IGNORECASE,
    ),
    "limitations": re.compile(
        r"\b(limitations?|weakness(?:es)?|constraints?|caveats?|shortcomings?|oversimplification|future work|further work)\b",
        re.IGNORECASE,
    ),
}


def _is_dimension_evidence(
    dimension: str,
    text: str,
) -> bool:
    return bool(
        DIMENSION_EVIDENCE_PATTERNS[dimension].search(text)
    )


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

        sources: dict[str, dict[str, list[Citation]]] = {}

        dimension_queries = {
            "problem": (
                "research problem, objective, challenge, or motivation addressed"
            ),
            "method": (
                "proposed method, model, algorithm, or experimental approach"
            ),
            "dataset": (
                "dataset, data source, sample size, or experimental data used"
            ),
            "metrics": (
                "evaluation metrics and performance measures reported"
            ),
            "results": (
                "quantitative experimental results and main findings"
            ),
            "limitations": (
                "stated limitations, weaknesses, assumptions, and future work"
            ),
        }

        for paper in papers:
            paper_sources: dict[str, list[Citation]] = {}

            for dimension, query in dimension_queries.items():
                citations = [
                    citation
                    for citation in search(
                        query=query,
                        paper_ids=[paper.id],
                        top_k=10,
                    )
                    if _is_dimension_evidence(
                        dimension,
                        citation.text,
                    )
                ][:1]

                paper_sources[dimension] = citations

            sources[paper.id] = paper_sources

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
                [paper.id for paper in papers],
                sources,
            ),
            "charts": [],
        }

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception("Paper comparison failed")
        raise _error(
            502,
            "ANALYSIS_FAILED",
            "The papers could not be compared.",
        ) from exc


def _comparison_rows(
    paper_ids: list[str],
    sources: dict[str, dict[str, list[Citation]]],
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

        for paper_id in paper_ids:
            available_sources = sources.get(
                paper_id,
                {},
            ).get(dimension, [])
            citations = [
                {
                    "paper_id": source.paper_id,
                    "chunk_id": source.chunk_id,
                    "page": source.page,
                    "section": source.section,
                }
                for source in available_sources
            ]

            cells.append(
                {
                    "paper_id": paper_id,
                    "value": (
                        available_sources[0].text[:320].strip()
                        if available_sources
                        else "Not reported in retrieved evidence."
                    ),
                    "citations": citations,
                }
            )

        rows.append(
            {
                "dimension": dimension,
                "cells": cells,
            }
        )

    return rows