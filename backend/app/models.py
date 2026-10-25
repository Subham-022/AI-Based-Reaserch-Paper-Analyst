from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Paper(SQLModel, table=True):
    id: str = Field(
        primary_key=True,
        index=True,
    )

    file_hash: str = Field(
        unique=True,
        index=True,
    )

    original_filename: str

    source_type: str

    source_url: Optional[str] = None

    storage_path: str

    title: Optional[str] = None

    authors_json: Optional[str] = None

    venue: Optional[str] = None

    year: Optional[int] = None

    doi: Optional[str] = None

    arxiv_id: Optional[str] = None

    status: str = "queued"

    error_message: Optional[str] = None

    summary_json: Optional[str] = None

    created_at: datetime = Field(
        default_factory=utc_now,
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
    )


class IngestionJob(SQLModel, table=True):
    id: str = Field(
        primary_key=True,
        index=True,
    )

    paper_id: str = Field(
        index=True,
    )

    status: str = "queued"

    progress: int = 0

    stage: Optional[str] = None

    error_message: Optional[str] = None

    created_at: datetime = Field(
        default_factory=utc_now,
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
    )


class ChatSession(SQLModel, table=True):
    id: str = Field(
        primary_key=True,
        index=True,
    )

    title: Optional[str] = None

    created_at: datetime = Field(
        default_factory=utc_now,
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
    )


class ChatSessionPaper(SQLModel, table=True):
    session_id: str = Field(
        primary_key=True,
    )

    paper_id: str = Field(
        primary_key=True,
    )


class ChatMessage(SQLModel, table=True):
    id: str = Field(
        primary_key=True,
        index=True,
    )

    session_id: str = Field(
        index=True,
    )

    role: str

    content: str

    citations_json: Optional[str] = None

    created_at: datetime = Field(
        default_factory=utc_now,
    )


class Report(SQLModel, table=True):
    id: str = Field(
        primary_key=True,
        index=True,
    )

    title: str

    format: str

    storage_path: str

    paper_ids_json: str

    created_at: datetime = Field(
        default_factory=utc_now,
    )