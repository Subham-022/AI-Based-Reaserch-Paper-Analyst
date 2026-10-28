from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.config import (
    ALLOWED_URL_HOSTS,
    CHROMA_DIR,
    EMBEDDING_MODEL,
    LLM_MODEL,
    MAX_DOWNLOAD_BYTES,
    MAX_UPLOAD_BYTES,
    OLLAMA_BASE_URL,
    PDF_DIR,
)
from app.db import get_session
from app.models import (
    IngestionJob,
    Paper,
    utc_now,
)


router = APIRouter(
    prefix="/papers",
    tags=["papers"],
)


class URLRequest(BaseModel):
    url: str


class PaperSummaryResponse(BaseModel):
    paper_id: str
    summary: str
    problem: str
    approach: str
    main_result: str
    limitations: list[str] = Field(default_factory=list)
    key_findings: list[str] = Field(default_factory=list)
    methodology_details: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    evaluation_metrics: list[str] = Field(default_factory=list)
    quantitative_results: list[str] = Field(default_factory=list)
    equations_and_calculations: list[str] = Field(default_factory=list)
    analysis_of_visuals_and_tables: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)


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


def _safe_filename() -> str:
    return f"{uuid.uuid4().hex}.pdf"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def _validate_pdf_header(path: Path) -> bool:
    with path.open("rb") as file:
        return file.read(5) == b"%PDF-"


def _build_visual_context(parsed) -> str:
    parts: list[str] = []
    for figure in parsed.figures:
        parts.append(
            f"Figure caption, page {figure.page}: {figure.caption}"
        )
    for table in parsed.tables:
        rows = "\n".join(
            " | ".join(row) for row in table.rows
        )
        parts.append(
            f"Table, page {table.page}, {table.caption}:\n{rows}"
        )
    for equation in parsed.equations:
        parts.append(
            f"Calculation or equation, page {equation.page}: {equation.text}"
        )
    return "\n\n".join(parts)[:20000]


def _parse_url(url: str):
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise _error(
            400,
            "INVALID_URL",
            "The paper URL is invalid.",
        ) from exc

    if parsed.scheme.lower() != "https":
        raise _error(
            400,
            "INVALID_URL",
            "Only HTTPS paper URLs are supported.",
        )

    if parsed.username is not None or parsed.password is not None:
        raise _error(
            400,
            "INVALID_URL",
            "URLs containing credentials are not allowed.",
        )

    try:
        hostname = parsed.hostname
    except ValueError as exc:
        raise _error(
            400,
            "INVALID_URL",
            "The paper URL contains an invalid hostname.",
        ) from exc

    if not hostname:
        raise _error(
            400,
            "INVALID_URL",
            "The URL does not contain a valid hostname.",
        )

    hostname = hostname.lower().rstrip(".")
    return parsed, hostname


def _validate_url(
    url: str,
    allow_public_host: bool = False,
) -> str:
    parsed, hostname = _parse_url(url)

    if (
        hostname not in ALLOWED_URL_HOSTS
        and not allow_public_host
        and not parsed.path.lower().endswith(".pdf")
    ):
        raise _error(
            403,
            "URL_BLOCKED",
            "Only supported paper hosts or direct PDF URLs are allowed.",
        )

    _validate_hostname(hostname)
    return hostname


def _validate_hostname(hostname: str) -> None:
    try:
        addresses = socket.getaddrinfo(
            hostname,
            443,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise _error(
            403,
            "URL_BLOCKED",
            "The paper host could not be resolved.",
        ) from exc

    if not addresses:
        raise _error(
            403,
            "URL_BLOCKED",
            "The paper host could not be resolved.",
        )

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_unspecified
            or ip.is_reserved
        ):
            raise _error(
                403,
                "URL_BLOCKED",
                "The requested host is not allowed.",
            )


def _validate_redirect_url(url: str) -> None:
    _validate_url(url, allow_public_host=True)


def _download_pdf(
    url: str,
    destination: Path,
) -> None:
    current_url = url

    for _ in range(4):
        _validate_redirect_url(current_url)

        try:
            response = httpx.get(
                current_url,
                timeout=20,
                follow_redirects=False,
                headers={
                    "User-Agent": "ResearchPaperAnalyst/1.0"
                },
            )
        except httpx.HTTPError as exc:
            raise _error(
                502,
                "DOWNLOAD_FAILED",
                "The paper could not be downloaded.",
            ) from exc

        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("location")

            if not location:
                raise _error(
                    502,
                    "DOWNLOAD_FAILED",
                    "The paper server returned an invalid redirect.",
                )

            current_url = str(httpx.URL(current_url).join(location))
            continue

        if response.status_code != 200:
            raise _error(
                502,
                "DOWNLOAD_FAILED",
                "The paper server did not return the PDF.",
            )

        content_length = response.headers.get("content-length")

        if content_length:
            try:
                declared_size = int(content_length)
            except ValueError as exc:
                raise _error(
                    502,
                    "DOWNLOAD_FAILED",
                    "The paper server returned an invalid content length.",
                ) from exc

            if declared_size > MAX_DOWNLOAD_BYTES:
                raise _error(
                    413,
                    "FILE_TOO_LARGE",
                    "The paper exceeds the configured size limit.",
                )

        content = response.content

        if len(content) > MAX_DOWNLOAD_BYTES:
            raise _error(
                413,
                "FILE_TOO_LARGE",
                "The paper exceeds the configured size limit.",
            )

        destination.write_bytes(content)

        if not _validate_pdf_header(destination):
            destination.unlink(missing_ok=True)
            raise _error(
                415,
                "UNSUPPORTED_CONTENT",
                "The URL did not return a valid PDF.",
            )

        return

    raise _error(
        502,
        "DOWNLOAD_FAILED",
        "Too many redirects were returned by the paper server.",
    )


def _create_paper(
    session: Session,
    path: Path,
    filename: str,
    source_type: str,
    source_url: str | None,
) -> tuple[Paper, IngestionJob]:
    file_hash = _hash_file(path)

    existing = session.exec(
        select(Paper).where(Paper.file_hash == file_hash)
    ).first()

    if existing:
        path.unlink(missing_ok=True)

        job = session.exec(
            select(IngestionJob)
            .where(IngestionJob.paper_id == existing.id)
            .order_by(IngestionJob.created_at.desc())
        ).first()

        if job is None:
            job = IngestionJob(
                id=uuid.uuid4().hex,
                paper_id=existing.id,
                status=existing.status,
            )
            session.add(job)
            session.commit()
            session.refresh(job)

        return existing, job

    paper = Paper(
        id=uuid.uuid4().hex,
        file_hash=file_hash,
        original_filename=filename,
        source_type=source_type,
        source_url=source_url,
        storage_path=str(path),
        status="queued",
    )

    job = IngestionJob(
        id=uuid.uuid4().hex,
        paper_id=paper.id,
        status="queued",
        progress=0,
        stage="Queued",
    )

    session.add(paper)
    session.add(job)
    session.commit()
    session.refresh(paper)
    session.refresh(job)

    return paper, job


def _set_job(
    paper_id: str,
    job_id: str,
    status: str,
    progress: int,
    stage: str | None,
    error_message: str | None = None,
) -> None:
    from app.db import engine

    with Session(engine) as session:
        paper = session.get(Paper, paper_id)
        job = session.get(IngestionJob, job_id)

        if paper is None or job is None:
            return

        paper.status = status
        paper.updated_at = utc_now()

        job.status = status
        job.progress = progress
        job.stage = stage
        job.error_message = error_message
        job.updated_at = utc_now()

        paper.error_message = error_message

        session.add(paper)
        session.add(job)
        session.commit()


def _run_ingestion(
    paper_id: str,
    job_id: str,
) -> None:
    from app.db import engine

    try:
        _set_job(
            paper_id,
            job_id,
            "processing",
            10,
            "Extracting text",
        )

        with Session(engine) as session:
            paper = session.get(Paper, paper_id)

            if paper is None:
                return

            pdf_path = Path(paper.storage_path)
            source_url = paper.source_url
            original_filename = paper.original_filename

        from app.ingestion.loader import load_file
        from app.ingestion.parser import parse_pdf

        pdf_data = load_file(pdf_path)
        parsed = parse_pdf(pdf_data)

        page_texts = [page.text for page in parsed.pages]

        extracted_characters = sum(
            len(text.strip()) for text in page_texts
        )

        if extracted_characters < 100:
            raise RuntimeError(
                "OCR_REQUIRED: This PDF does not contain enough "
                "extractable text. OCR is required."
            )

        _set_job(
            paper_id,
            job_id,
            "processing",
            30,
            "Cleaning paper",
        )

        from app.ingestion.cleaner import clean_pages

        cleaned_pages = clean_pages(page_texts)

        cleaned_characters = sum(
            len(text.strip()) for text in cleaned_pages
        )

        if cleaned_characters < 100:
            raise RuntimeError(
                "OCR_REQUIRED: No usable paper text was extracted "
                "after cleaning. OCR is required."
            )

        _set_job(
            paper_id,
            job_id,
            "processing",
            45,
            "Detecting sections",
        )

        from app.ingestion.sectioner import (
            chunk_sections,
            detect_sections,
        )

        page_pairs = [
            (page.page, cleaned_pages[index])
            for index, page in enumerate(parsed.pages)
        ]

        sections = detect_sections(page_pairs)

        if not sections:
            raise RuntimeError(
                "No research paper sections could be extracted."
            )

        _set_job(
            paper_id,
            job_id,
            "processing",
            55,
            "Extracting metadata",
        )

        from app.ingestion.metadata import extract_metadata

        metadata = extract_metadata(
            cleaned_pages,
            source_url=source_url,
            pdf_metadata=parsed.metadata,
            fallback_title=Path(original_filename).stem,
        )

        _set_job(
            paper_id,
            job_id,
            "processing",
            65,
            "Creating embeddings",
        )

        chunks = chunk_sections(paper_id, sections)

        if not chunks:
            raise RuntimeError(
                "No searchable text chunks could be created."
            )

        from app.retrieval.embedder import Embedder

        embedder = Embedder(model_name=EMBEDDING_MODEL)
        embeddings = embedder.embed(
            [chunk.text for chunk in chunks]
        )

        _set_job(
            paper_id,
            job_id,
            "processing",
            80,
            "Indexing chunks",
        )

        from app.retrieval.store import VectorStore

        store = VectorStore(CHROMA_DIR)
        store.add(chunks, embeddings)

        print("VECTOR INDEXING COMPLETE")

        _set_job(
            paper_id,
            job_id,
            "processing",
            90,
            "Generating summary",
        )

        print("SUMMARY STAGE START")

        from app.llm.ollama_client import OllamaClient

        print(f"Using Ollama model: {LLM_MODEL}")
        llm = OllamaClient(
            base_url=OLLAMA_BASE_URL,
            model=LLM_MODEL,
        )

        from app.analysis.summarize import summarize_paper

        section_pairs = [
            (f"{section.name} (page {page_number})", page_text)
            for section in sections
            for page_number, page_text in (
                section.page_parts
                or ((section.start_page, section.text),)
            )
        ]

        print(
            f"CALLING LLM FOR SUMMARY: {len(section_pairs)} sections"
        )

        summary = summarize_paper(
            llm,
            section_pairs,
            visual_context=_build_visual_context(parsed),
        )

        print("LLM SUMMARY COMPLETE")

        with Session(engine) as session:
            paper = session.get(Paper, paper_id)

            if paper is None:
                return

            paper.title = metadata.title
            paper.authors_json = json.dumps(metadata.authors)
            paper.venue = metadata.venue
            paper.year = metadata.year
            paper.doi = metadata.doi
            paper.arxiv_id = metadata.arxiv_id
            paper.summary_json = summary.model_dump_json()
            paper.status = "ready"
            paper.error_message = None
            paper.updated_at = utc_now()

            session.add(paper)
            session.commit()

        _set_job(
            paper_id,
            job_id,
            "ready",
            100,
            "Ready",
        )

        print("PAPER INGESTION COMPLETE")

    except Exception as exc:
        message = str(exc) or "Paper ingestion failed."

        print(f"INGESTION FAILED: {message}")

        _set_job(
            paper_id,
            job_id,
            "failed",
            100,
            "Failed",
            message,
        )


@router.post("/upload", status_code=202)
async def upload_paper(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    filename = file.filename or ""

    if not filename.lower().endswith(".pdf"):
        await file.close()
        raise _error(
            415,
            "UNSUPPORTED_FILE",
            "Only PDF files are supported.",
        )

    destination = PDF_DIR / _safe_filename()
    total = 0

    try:
        # Close the output file before any attempt to delete it.
        with destination.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                total += len(chunk)

                if total > MAX_UPLOAD_BYTES:
                    raise _error(
                        413,
                        "FILE_TOO_LARGE",
                        "The PDF exceeds the configured size limit.",
                    )

                output.write(chunk)

        if not _validate_pdf_header(destination):
            raise _error(
                415,
                "UNSUPPORTED_FILE",
                "The uploaded file is not a valid PDF.",
            )

    except Exception:
        # The output file has closed before this cleanup runs.
        destination.unlink(missing_ok=True)
        raise

    finally:
        await file.close()

    try:
        paper, job = _create_paper(
            session,
            destination,
            filename,
            "upload",
            None,
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    if paper.status != "ready":
        background_tasks.add_task(
            _run_ingestion,
            paper.id,
            job.id,
        )

    return {
        "paper_id": paper.id,
        "job_id": job.id,
        "status": paper.status,
    }


@router.post("/url", status_code=202)
def ingest_url(
    request: URLRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict:
    _validate_url(request.url)

    destination = PDF_DIR / _safe_filename()

    try:
        _download_pdf(request.url, destination)
        paper, job = _create_paper(
            session,
            destination,
            "remote-paper.pdf",
            "url",
            request.url,
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    if paper.status != "ready":
        background_tasks.add_task(
            _run_ingestion,
            paper.id,
            job.id,
        )

    return {
        "paper_id": paper.id,
        "job_id": job.id,
        "status": paper.status,
    }


@router.get("")
def list_papers(
    session: Session = Depends(get_session),
) -> dict:
    papers = session.exec(
        select(Paper).order_by(Paper.created_at.desc())
    ).all()

    return {
        "items": [
            {
                "id": paper.id,
                "title": paper.title or paper.original_filename,
                "year": paper.year,
                "status": paper.status,
            }
            for paper in papers
        ]
    }


@router.get("/{paper_id}")
def get_paper(
    paper_id: str,
    session: Session = Depends(get_session),
) -> dict:
    paper = session.get(Paper, paper_id)

    if paper is None:
        raise _error(
            404,
            "PAPER_NOT_FOUND",
            "The requested paper does not exist.",
        )

    return {
        "id": paper.id,
        "title": paper.title,
        "authors": json.loads(paper.authors_json or "[]"),
        "venue": paper.venue,
        "year": paper.year,
        "doi": paper.doi,
        "arxiv_id": paper.arxiv_id,
        "status": paper.status,
    }


@router.post(
    "/{paper_id}/reprocess",
    status_code=202,
)
def reprocess_paper(
    paper_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict:
    paper = session.get(Paper, paper_id)

    if paper is None:
        raise _error(
            404,
            "PAPER_NOT_FOUND",
            "The requested paper does not exist.",
        )

    if paper.status in {"queued", "processing"}:
        raise _error(
            409,
            "PAPER_ALREADY_PROCESSING",
            "The paper is already being processed.",
        )

    if not Path(paper.storage_path).is_file():
        raise _error(
            410,
            "PDF_NOT_FOUND",
            "The stored PDF is unavailable and cannot be reprocessed.",
        )

    job = IngestionJob(
        id=uuid.uuid4().hex,
        paper_id=paper.id,
        status="queued",
        progress=0,
        stage="Queued",
    )
    paper.status = "queued"
    paper.error_message = None
    paper.updated_at = utc_now()
    session.add(paper)
    session.add(job)
    session.commit()

    background_tasks.add_task(
        _run_ingestion,
        paper.id,
        job.id,
    )

    return {
        "paper_id": paper.id,
        "job_id": job.id,
        "status": paper.status,
    }


@router.get("/{paper_id}/status")
def paper_status(
    paper_id: str,
    session: Session = Depends(get_session),
) -> dict:
    paper = session.get(Paper, paper_id)

    if paper is None:
        raise _error(
            404,
            "PAPER_NOT_FOUND",
            "The requested paper does not exist.",
        )

    job = session.exec(
        select(IngestionJob)
        .where(IngestionJob.paper_id == paper_id)
        .order_by(IngestionJob.created_at.desc())
    ).first()

    if job is None:
        return {
            "paper_id": paper_id,
            "status": paper.status,
            "progress": 0,
            "stage": None,
            "error": paper.error_message,
        }

    return {
        "paper_id": paper_id,
        "status": job.status,
        "progress": job.progress,
        "stage": job.stage,
        "error": job.error_message,
    }


@router.get("/{paper_id}/source/{chunk_id}")
def get_paper_source(
    paper_id: str,
    chunk_id: str,
    session: Session = Depends(get_session),
) -> dict:
    paper = session.get(Paper, paper_id)

    if paper is None:
        raise _error(
            404,
            "PAPER_NOT_FOUND",
            "The requested paper does not exist.",
        )

    if paper.status != "ready":
        raise _error(
            409,
            "PAPER_NOT_READY",
            "The paper has not finished processing.",
        )

    from app.retrieval.search import get_retriever

    source = get_retriever().store.get_chunk(chunk_id)

    if (
        source is None
        or source["metadata"].get("paper_id") != paper_id
        or source["metadata"].get("chunk_id") != chunk_id
    ):
        raise _error(
            404,
            "SOURCE_NOT_FOUND",
            "The requested source passage does not exist.",
        )

    metadata = source["metadata"]
    return {
        "paper_id": paper_id,
        "chunk_id": chunk_id,
        "page": int(metadata["page"]),
        "section": str(metadata["section"]),
        "text": str(source["text"]),
    }


@router.get(
    "/{paper_id}/summary",
    response_model=PaperSummaryResponse,
)
def get_summary(
    paper_id: str,
    session: Session = Depends(get_session),
) -> PaperSummaryResponse:
    paper = session.get(Paper, paper_id)

    if paper is None:
        raise _error(
            404,
            "PAPER_NOT_FOUND",
            "The requested paper does not exist.",
        )

    if paper.status != "ready":
        raise _error(
            409,
            "PAPER_NOT_READY",
            "The paper has not finished processing.",
        )

    if not paper.summary_json:
        raise _error(
            502,
            "ANALYSIS_FAILED",
            "No cached paper summary is available.",
        )

    data = json.loads(paper.summary_json)

    return PaperSummaryResponse(
        paper_id=paper.id,
        summary=data["summary"],
        problem=data["problem"],
        approach=data["approach"],
        main_result=data["main_result"],
        limitations=data.get("limitations", []),
        key_findings=data.get("key_findings", []),
        methodology_details=data.get("methodology_details", []),
        datasets=data.get("datasets", []),
        evaluation_metrics=data.get("evaluation_metrics", []),
        quantitative_results=data.get("quantitative_results", []),
        equations_and_calculations=data.get(
            "equations_and_calculations",
            [],
        ),
        analysis_of_visuals_and_tables=data.get(
            "analysis_of_visuals_and_tables",
            [],
        ),
        key_points=[
            data["problem"],
            data["approach"],
            data["main_result"],
            *data.get("limitations", []),
        ],
        citations=[],
    )


@router.get("/{paper_id}/assets")
def get_paper_assets(
    paper_id: str,
    session: Session = Depends(get_session),
) -> dict:
    paper = session.get(Paper, paper_id)
    if paper is None:
        raise _error(
            404,
            "PAPER_NOT_FOUND",
            "The requested paper does not exist.",
        )
    if paper.status != "ready":
        raise _error(
            409,
            "PAPER_NOT_READY",
            "Paper visuals are available after processing completes.",
        )

    from app.ingestion.loader import load_file
    from app.ingestion.parser import parse_pdf

    try:
        parsed = parse_pdf(load_file(Path(paper.storage_path)))
    except (OSError, ValueError) as exc:
        raise _error(
            422,
            "ASSET_EXTRACTION_FAILED",
            "The stored PDF could not be read to extract its figures and tables.",
        ) from exc

    return {
        "paper_id": paper_id,
        "figures": [
            {
                "page": figure.page,
                "xref": figure.xref,
                "caption": figure.caption,
                "image_url": (
                    f"/api/papers/{paper_id}/figures/"
                    f"{figure.page}/{figure.xref}"
                ),
            }
            for figure in parsed.figures
        ],
        "tables": [
            {
                "page": table.page,
                "caption": table.caption,
                "rows": table.rows,
                "preview_only": table.preview_only,
                "preview_url": (
                    f"/api/papers/{paper_id}/tables/"
                    f"{table.page}/"
                    f"{sum(1 for previous in parsed.tables[:index] if previous.page == table.page)}"
                    "/preview"
                ),
            }
            for index, table in enumerate(parsed.tables)
        ],
        "equations": [
            {
                "page": equation.page,
                "text": equation.text,
            }
            for equation in parsed.equations
        ],
    }


@router.get("/{paper_id}/figures/{page_number}/{xref}")
def get_paper_figure(
    paper_id: str,
    page_number: int,
    xref: int,
    session: Session = Depends(get_session),
) -> Response:
    paper = session.get(Paper, paper_id)
    if paper is None:
        raise _error(
            404,
            "PAPER_NOT_FOUND",
            "The requested paper does not exist.",
        )
    if paper.status != "ready":
        raise _error(
            409,
            "PAPER_NOT_READY",
            "Paper figures are available after processing completes.",
        )

    from app.ingestion.loader import load_file
    from app.ingestion.parser import extract_figure_image

    try:
        image, media_type = extract_figure_image(
            load_file(Path(paper.storage_path)),
            page_number,
            xref,
        )
    except (OSError, ValueError) as exc:
        raise _error(
            404,
            "FIGURE_NOT_FOUND",
            "The requested figure could not be extracted from the PDF.",
        ) from exc

    return Response(
        content=image,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/{paper_id}/tables/{page_number}/{table_index}/preview")
def get_paper_table_preview(
    paper_id: str,
    page_number: int,
    table_index: int,
    session: Session = Depends(get_session),
) -> Response:
    paper = session.get(Paper, paper_id)
    if paper is None:
        raise _error(
            404,
            "PAPER_NOT_FOUND",
            "The requested paper does not exist.",
        )
    if paper.status != "ready":
        raise _error(
            409,
            "PAPER_NOT_READY",
            "Paper table previews are available after processing completes.",
        )

    from app.ingestion.loader import load_file
    from app.ingestion.parser import extract_table_preview

    try:
        image = extract_table_preview(
            load_file(Path(paper.storage_path)),
            page_number,
            table_index,
        )
    except (OSError, ValueError) as exc:
        raise _error(
            404,
            "TABLE_NOT_FOUND",
            "The requested table preview could not be extracted.",
        ) from exc

    return Response(
        content=image,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"},
    )