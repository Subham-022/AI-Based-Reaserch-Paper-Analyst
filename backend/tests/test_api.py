from __future__ import annotations

import io

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.db import get_session
from app.main import app
from app.api.papers import (
    _validate_url,
    _validate_hostname,
)


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