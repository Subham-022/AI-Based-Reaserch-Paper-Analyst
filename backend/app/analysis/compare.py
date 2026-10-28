from __future__ import annotations

from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    paper_id: str
    chunk_id: str
    page: int


class ComparisonCell(BaseModel):
    value: str
    citations: list[SourceCitation] = Field(
        default_factory=list
    )


class PaperComparison(BaseModel):
    paper_id: str
    problem: ComparisonCell
    method: ComparisonCell
    dataset: ComparisonCell
    metrics: ComparisonCell
    results: ComparisonCell
    limitations: ComparisonCell


class ComparisonResult(BaseModel):
    papers: list[PaperComparison]
