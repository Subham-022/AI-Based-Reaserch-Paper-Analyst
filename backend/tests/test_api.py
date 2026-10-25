from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.db import get_session
from app.main import app
from app.api import papers as papers_api
from app.api import compare as compare_api
from app.api import reports as reports_api
from app.analysis.summarize import SummaryResult
from app.api.papers import (
    URLRequest,
    _validate_url,
    _validate_hostname,
)
from app.api.compare import (
    _comparison_rows,
    _is_dimension_evidence,
)
from app.models import Paper
from app.retrieval.search import Citation
import app.retrieval.search as retrieval_search


engine = create_engine(
    "sqlite://",
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)


SQLModel.metadata.create_all(
    engine
)


def override_session():
    with Session(engine) as session:
        yield session


app.dependency_overrides[
    get_session
] = override_session


client = TestClient(app)


def test_health() -> None:
    response = client.get(
        "/health"
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok"
    }


def test_empty_paper_library() -> None:
    response = client.get(
        "/api/papers"
    )

    assert response.status_code == 200
    assert "items" in response.json()


def test_paper_summary_returns_structured_analysis() -> None:
    summary = {
        "summary": "A concise paper summary.",
        "problem": "The research problem.",
        "approach": "The proposed approach.",
        "main_result": "The main result.",
        "limitations": ["A stated limitation."],
    }

    with Session(engine) as session:
        session.add(
            Paper(
                id="summary-paper",
                file_hash="summary-paper-hash",
                original_filename="summary.pdf",
                source_type="upload",
                storage_path="summary.pdf",
                status="ready",
                summary_json=json.dumps(summary),
            )
        )
        session.commit()

    response = client.get(
        "/api/papers/summary-paper/summary"
    )

    assert response.status_code == 200
    assert response.json()["problem"] == "The research problem."
    assert response.json()["approach"] == "The proposed approach."
    assert response.json()["main_result"] == "The main result."
    assert response.json()["limitations"] == ["A stated limitation."]


def test_paper_source_returns_only_the_requested_papers_chunk(
    monkeypatch,
) -> None:
    paper_id = "source-route-paper"
    chunk_id = f"{paper_id}:12"

    with Session(engine) as session:
        session.add(
            Paper(
                id=paper_id,
                file_hash=f"{paper_id}-hash",
                original_filename="source-paper.pdf",
                source_type="upload",
                storage_path="source-paper.pdf",
                status="ready",
            )
        )
        session.commit()

    def get_chunk(requested_chunk_id):
        if requested_chunk_id == f"{paper_id}:foreign":
            return {
                "text": "Another paper's passage.",
                "metadata": {
                    "paper_id": "another-paper",
                    "chunk_id": requested_chunk_id,
                    "page": 8,
                    "section": "methods",
                },
            }
        if requested_chunk_id != chunk_id:
            return None
        return {
            "text": "Exact source passage.",
            "metadata": {
                "paper_id": paper_id,
                "chunk_id": chunk_id,
                "page": 4,
                "section": "results",
            },
        }

    monkeypatch.setattr(
        retrieval_search,
        "get_retriever",
        lambda: SimpleNamespace(
            store=SimpleNamespace(get_chunk=get_chunk)
        ),
    )

    response = client.get(
        f"/api/papers/{paper_id}/source/{chunk_id}"
    )

    assert response.status_code == 200
    assert response.json() == {
        "paper_id": paper_id,
        "chunk_id": chunk_id,
        "page": 4,
        "section": "results",
        "text": "Exact source passage.",
    }

    missing = client.get(
        f"/api/papers/{paper_id}/source/{paper_id}:missing"
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["error"]["code"] == "SOURCE_NOT_FOUND"

    foreign = client.get(
        f"/api/papers/{paper_id}/source/{paper_id}:foreign"
    )
    assert foreign.status_code == 404
    assert foreign.json()["detail"]["error"]["code"] == "SOURCE_NOT_FOUND"


def test_comparison_rows_show_retrieved_passages_and_citations() -> None:
    paper_id = "comparison-paper"
    retrieved = Citation(
        paper_id=paper_id,
        chunk_id="real-chunk",
        section="introduction",
        page=4,
        text="A retrieved passage supporting the problem.",
        score=0.8,
    )

    rows = _comparison_rows(
        [paper_id],
        {
            paper_id: {
                "problem": [retrieved],
                "method": [],
                "dataset": [],
            }
        },
    )

    assert rows[0]["cells"][0]["value"] == (
        "A retrieved passage supporting the problem."
    )
    assert rows[0]["cells"][0]["citations"] == [
        {
            "paper_id": paper_id,
            "chunk_id": "real-chunk",
            "page": 4,
            "section": "introduction",
        }
    ]
    assert rows[1]["cells"][0]["value"] == (
        "Not reported in retrieved evidence."
    )
    assert rows[1]["cells"][0]["citations"] == []
    assert rows[2]["cells"][0]["value"] == (
        "Not reported in retrieved evidence."
    )
    assert rows[2]["cells"][0]["citations"] == []


def test_comparison_rejects_passages_unrelated_to_their_dimension() -> None:
    assert not _is_dimension_evidence(
        "limitations",
        "23 of 26. Conflicts of interest: none.",
    )
    assert not _is_dimension_evidence(
        "dataset",
        "A schematic depiction of sensors and perception.",
    )
    assert _is_dimension_evidence(
        "metrics",
        "Accuracy = 90.48% and F1-score = 0.88.",
    )
    assert _is_dimension_evidence(
        "limitations",
        "The main limitation is the small sample size.",
    )


def test_upload_rejects_non_pdf() -> None:
    response = client.post(
        "/api/papers/upload",
        files={
            "file": (
                "notes.txt",
                io.BytesIO(
                    b"not a pdf"
                ),
                "text/plain",
            )
        },
    )

    assert response.status_code == 415

    data = response.json()

    assert (
        data["detail"]["error"]["code"]
        == "UNSUPPORTED_FILE"
    )


def test_url_ingest_reports_malformed_url_without_server_error() -> None:
    response = client.post(
        "/api/papers/url",
        json={"url": "https://[::1/paper.pdf"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "INVALID_URL"


def test_url_ingest_removes_download_if_paper_creation_fails(
    monkeypatch,
    tmp_path,
) -> None:
    destination = tmp_path / "download.pdf"
    monkeypatch.setattr(papers_api, "PDF_DIR", tmp_path)
    monkeypatch.setattr(
        papers_api,
        "_safe_filename",
        lambda: destination.name,
    )
    monkeypatch.setattr(
        papers_api,
        "_validate_url",
        lambda url: "example.com",
    )
    monkeypatch.setattr(
        papers_api,
        "_download_pdf",
        lambda url, path: path.write_bytes(b"%PDF-test"),
    )

    def fail_create(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        papers_api,
        "_create_paper",
        fail_create,
    )

    with Session(engine) as session:
        with pytest.raises(RuntimeError, match="database unavailable"):
            papers_api.ingest_url(
                URLRequest(url="https://example.com/paper.pdf"),
                BackgroundTasks(),
                session,
            )

    assert not destination.exists()


def test_question_requires_text() -> None:
    response = client.post(
        "/api/chat/questions",
        json={
            "session_id": "missing",
            "question": "",
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert (
        data["detail"]["error"]["code"]
        == "INVALID_QUESTION"
    )


def test_invalid_report_format() -> None:
    response = client.post(
        "/api/reports",
        json={
            "paper_ids": ["missing"],
            "format": "docx",
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert (
        data["detail"]["error"]["code"]
        == "INVALID_FORMAT"
    )


def test_compare_requires_two_papers() -> None:
    response = client.post(
        "/api/compare",
        json={
            "paper_ids": [
                "paper-1"
            ]
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert (
        data["detail"]["error"]["code"]
        == "TOO_FEW_PAPERS"
    )


def test_compare_route_returns_verified_evidence(
    monkeypatch,
) -> None:
    paper_ids = [
        "compare-route-paper-1",
        "compare-route-paper-2",
    ]

    with Session(engine) as session:
        for paper_id in paper_ids:
            session.add(
                Paper(
                    id=paper_id,
                    file_hash=f"{paper_id}-hash",
                    original_filename=f"{paper_id}.pdf",
                    source_type="upload",
                    storage_path=f"{paper_id}.pdf",
                    status="ready",
                )
            )
        session.commit()

    def fake_search(query, paper_ids, **kwargs):
        assert kwargs["top_k"] == 10
        paper_id = paper_ids[0]
        return [
            Citation(
                paper_id=paper_id,
                chunk_id=f"{paper_id}-low-confidence",
                section="results",
                page=2,
                text="Low-confidence unrelated passage.",
                score=0.08,
            ),
            Citation(
                paper_id=paper_id,
                chunk_id=f"{paper_id}-chunk",
                section="results",
                page=5,
                text=(
                    f"The research problem and objective are "
                    f"documented for {paper_id}."
                ),
                score=0.2,
            )
        ]

    monkeypatch.setattr(
        retrieval_search,
        "search",
        fake_search,
    )
    response = client.post(
        "/api/compare",
        json={"paper_ids": paper_ids},
    )

    assert response.status_code == 200
    result = response.json()
    assert [paper["id"] for paper in result["papers"]] == paper_ids
    assert result["rows"][0]["cells"][0] == {
        "paper_id": paper_ids[0],
        "value": (
            f"The research problem and objective are "
            f"documented for {paper_ids[0]}."
        ),
        "citations": [
            {
                "paper_id": paper_ids[0],
                "chunk_id": f"{paper_ids[0]}-chunk",
                "page": 5,
                "section": "results",
            }
        ],
    }


def test_report_route_creates_and_downloads_markdown(
    monkeypatch,
    tmp_path,
) -> None:
    paper_id = "report-route-paper"
    summary = SummaryResult(
        summary="Summary text.",
        problem="Problem text.",
        approach="Approach text.",
        main_result="Result text.",
        limitations=["Limitation text."],
    )

    with Session(engine) as session:
        session.add(
            Paper(
                id=paper_id,
                file_hash=f"{paper_id}-hash",
                original_filename="report-paper.pdf",
                source_type="upload",
                storage_path="report-paper.pdf",
                status="ready",
                summary_json=summary.model_dump_json(),
            )
        )
        session.commit()

    monkeypatch.setattr(
        reports_api,
        "REPORT_DIR",
        tmp_path,
    )
    monkeypatch.setattr(
        retrieval_search,
        "search",
        lambda **kwargs: [
            Citation(
                paper_id=paper_id,
                chunk_id="report-chunk",
                section="results",
                page=3,
                text="Retrieved report evidence.",
                score=0.9,
            )
        ],
    )

    response = client.post(
        "/api/reports",
        json={
            "paper_ids": [paper_id],
            "format": "md",
        },
    )

    assert response.status_code == 200
    report_id = response.json()["report_id"]

    download = client.get(
        f"/api/reports/{report_id}/download"
    )

    assert download.status_code == 200
    assert "# report-paper" in download.text
    assert "## Executive Summary" in download.text
    assert "Retrieved report evidence." in download.text
    assert "- Limitation text. (from saved paper analysis)" in download.text


def test_pdf_report_failure_removes_partial_files_and_database_record(
    monkeypatch,
    tmp_path,
) -> None:
    paper_id = "failed-pdf-report-paper"
    summary = SummaryResult(
        summary="Summary text.",
        problem="Problem text.",
        approach="Approach text.",
        main_result="Result text.",
        limitations=[],
    )

    with Session(engine) as session:
        session.add(
            Paper(
                id=paper_id,
                file_hash=f"{paper_id}-hash",
                original_filename="failed-report.pdf",
                source_type="upload",
                storage_path="failed-report.pdf",
                status="ready",
                summary_json=summary.model_dump_json(),
            )
        )
        session.commit()

    monkeypatch.setattr(
        reports_api,
        "REPORT_DIR",
        tmp_path,
    )
    monkeypatch.setattr(
        retrieval_search,
        "search",
        lambda **kwargs: [],
    )

    def fail_after_writing(markdown, path):
        path.write_bytes(b"%PDF-partial")
        raise OSError("PDF renderer failed")

    monkeypatch.setattr(
        "app.reports.pdf.export_pdf",
        fail_after_writing,
    )

    response = client.post(
        "/api/reports",
        json={
            "paper_ids": [paper_id],
            "format": "pdf",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"]["error"]["code"] == "REPORT_FAILED"
    assert list(tmp_path.iterdir()) == []


def test_multi_paper_report_includes_comparison_table(
    monkeypatch,
    tmp_path,
) -> None:
    paper_ids = [
        "multi-report-paper-1",
        "multi-report-paper-2",
    ]
    summaries = [
        SummaryResult(
            summary=f"Summary for {paper_id}.",
            problem=f"Problem for {paper_id}.",
            approach=f"Method for {paper_id}.",
            main_result=f"Result for {paper_id}.",
            limitations=[],
        )
        for paper_id in paper_ids
    ]

    with Session(engine) as session:
        for index, paper_id in enumerate(paper_ids):
            session.add(
                Paper(
                    id=paper_id,
                    file_hash=f"{paper_id}-hash",
                    original_filename=f"{paper_id}.pdf",
                    title=f"Title {index + 1}",
                    source_type="upload",
                    storage_path=f"{paper_id}.pdf",
                    status="ready",
                    summary_json=summaries[index].model_dump_json(),
                )
            )
        session.commit()

    monkeypatch.setattr(
        reports_api,
        "REPORT_DIR",
        tmp_path,
    )
    monkeypatch.setattr(
        retrieval_search,
        "search",
        lambda **kwargs: [],
    )

    dimensions = [
        "problem",
        "method",
        "dataset",
        "metrics",
        "results",
        "limitations",
    ]

    def fake_compare(request, session):
        return {
            "rows": [
                {
                    "dimension": dimension,
                    "cells": [
                        {
                            "paper_id": paper_id,
                            "value": f"{dimension} evidence for {paper_id}",
                            "citations": [],
                        }
                        for paper_id in request.paper_ids
                    ],
                }
                for dimension in dimensions
            ]
        }

    monkeypatch.setattr(
        compare_api,
        "compare_papers",
        fake_compare,
    )

    response = client.post(
        "/api/reports",
        json={
            "paper_ids": paper_ids,
            "format": "md",
        },
    )

    assert response.status_code == 200
    report_id = response.json()["report_id"]
    download = client.get(
        f"/api/reports/{report_id}/download"
    )
    assert download.status_code == 200
    assert "## Comparison" in download.text
    assert "| Title 1 |" in download.text
    assert "problem evidence for multi-report-paper-1" in download.text
    assert "| Title 2 |" in download.text
    assert "metrics evidence for multi-report-paper-2" in download.text


def test_validate_url_rejects_http() -> None:
    try:
        _validate_url(
            "http://arxiv.org/pdf/1234.5678.pdf"
        )
    except Exception as exc:
        assert getattr(
            exc,
            "status_code",
            None,
        ) == 400
    else:
        raise AssertionError(
            "HTTP URLs must be rejected."
        )


def test_validate_url_accepts_arxiv(
    monkeypatch,
) -> None:
    def fake_getaddrinfo(
        *args,
        **kwargs,
    ):
        return [
            (
                2,
                1,
                6,
                "",
                (
                    "151.101.3.42",
                    443,
                ),
            )
        ]

    monkeypatch.setattr(
        "socket.getaddrinfo",
        fake_getaddrinfo,
    )

    hostname = _validate_url(
        "https://arxiv.org/pdf/1234.5678.pdf"
    )

    assert hostname == "arxiv.org"


def test_validate_url_accepts_doi(
    monkeypatch,
) -> None:
    def fake_getaddrinfo(
        *args,
        **kwargs,
    ):
        return [
            (
                2,
                1,
                6,
                "",
                (
                    "104.18.0.100",
                    443,
                ),
            )
        ]

    monkeypatch.setattr(
        "socket.getaddrinfo",
        fake_getaddrinfo,
    )

    hostname = _validate_url(
        "https://doi.org/10.1000/example"
    )

    assert hostname == "doi.org"


def test_validate_url_accepts_dx_doi(
    monkeypatch,
) -> None:
    def fake_getaddrinfo(
        *args,
        **kwargs,
    ):
        return [
            (
                2,
                1,
                6,
                "",
                (
                    "104.18.0.100",
                    443,
                ),
            )
        ]

    monkeypatch.setattr(
        "socket.getaddrinfo",
        fake_getaddrinfo,
    )

    hostname = _validate_url(
        "https://dx.doi.org/10.1000/example"
    )

    assert hostname == "dx.doi.org"


def test_validate_url_rejects_non_pdf_public_host(
    monkeypatch,
) -> None:
    def fake_getaddrinfo(
        *args,
        **kwargs,
    ):
        return [
            (
                2,
                1,
                6,
                "",
                (
                    "93.184.216.34",
                    443,
                ),
            )
        ]

    monkeypatch.setattr(
        "socket.getaddrinfo",
        fake_getaddrinfo,
    )

    try:
        _validate_url(
            "https://example.com/paper"
        )
    except Exception as exc:
        assert getattr(
            exc,
            "status_code",
            None,
        ) == 403
    else:
        raise AssertionError(
            "Non-PDF URLs on unsupported hosts must be rejected."
        )


def test_validate_url_accepts_direct_pdf(
    monkeypatch,
) -> None:
    def fake_getaddrinfo(
        *args,
        **kwargs,
    ):
        return [
            (
                2,
                1,
                6,
                "",
                (
                    "93.184.216.34",
                    443,
                ),
            )
        ]

    monkeypatch.setattr(
        "socket.getaddrinfo",
        fake_getaddrinfo,
    )

    hostname = _validate_url(
        "https://example.com/paper.pdf"
    )

    assert hostname == "example.com"


def test_validate_url_rejects_credentials() -> None:
    try:
        _validate_url(
            "https://user:password@arxiv.org/pdf/1234.5678.pdf"
        )
    except Exception as exc:
        assert getattr(
            exc,
            "status_code",
            None,
        ) == 400
    else:
        raise AssertionError(
            "URLs containing credentials must be rejected."
        )


def test_validate_url_rejects_missing_hostname() -> None:
    try:
        _validate_url(
            "https:///pdf/paper.pdf"
        )
    except Exception as exc:
        assert getattr(
            exc,
            "status_code",
            None,
        ) == 400
    else:
        raise AssertionError(
            "URLs without a hostname must be rejected."
        )


def test_validate_hostname_rejects_private_ip(
    monkeypatch,
) -> None:
    def fake_getaddrinfo(
        *args,
        **kwargs,
    ):
        return [
            (
                2,
                1,
                6,
                "",
                (
                    "192.168.1.10",
                    443,
                ),
            )
        ]

    monkeypatch.setattr(
        "socket.getaddrinfo",
        fake_getaddrinfo,
    )

    try:
        _validate_hostname(
            "example.com"
        )
    except Exception as exc:
        assert getattr(
            exc,
            "status_code",
            None,
        ) == 403
    else:
        raise AssertionError(
            "Private IP addresses must be rejected."
        )


def test_validate_hostname_rejects_loopback_ip(
    monkeypatch,
) -> None:
    def fake_getaddrinfo(
        *args,
        **kwargs,
    ):
        return [
            (
                2,
                1,
                6,
                "",
                (
                    "127.0.0.1",
                    443,
                ),
            )
        ]

    monkeypatch.setattr(
        "socket.getaddrinfo",
        fake_getaddrinfo,
    )

    try:
        _validate_hostname(
            "example.com"
        )
    except Exception as exc:
        assert getattr(
            exc,
            "status_code",
            None,
        ) == 403
    else:
        raise AssertionError(
            "Loopback IP addresses must be rejected."
        )


def test_validate_hostname_rejects_link_local_ip(
    monkeypatch,
) -> None:
    def fake_getaddrinfo(
        *args,
        **kwargs,
    ):
        return [
            (
                2,
                1,
                6,
                "",
                (
                    "169.254.1.10",
                    443,
                ),
            )
        ]

    monkeypatch.setattr(
        "socket.getaddrinfo",
        fake_getaddrinfo,
    )

    try:
        _validate_hostname(
            "example.com"
        )
    except Exception as exc:
        assert getattr(
            exc,
            "status_code",
            None,
        ) == 403
    else:
        raise AssertionError(
            "Link-local IP addresses must be rejected."
        )