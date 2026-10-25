
from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


DATA_DIR = Path(
    os.getenv(
        "DATA_DIR",
        str(BASE_DIR / "data"),
    )
)

STORAGE_DIR = DATA_DIR / "storage"
PDF_DIR = STORAGE_DIR / "papers"
REPORT_DIR = STORAGE_DIR / "reports"
CHART_DIR = STORAGE_DIR / "charts"
CHROMA_DIR = DATA_DIR / "chroma"


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DATA_DIR / 'research.db'}",
)


# Language model configuration
LLM_PROVIDER = os.getenv(
    "LLM_PROVIDER",
    "ollama",
).lower()

LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "llama3.2:3b",
)

LLM_API_KEY = os.getenv(
    "LLM_API_KEY"
)

LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://api.anthropic.com",
)


# Ollama local model server
OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://127.0.0.1:11434",
)


# Embedding model configuration
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)


# Upload and download limits
MAX_UPLOAD_MB = int(
    os.getenv(
        "MAX_UPLOAD_MB",
        "25",
    )
)

MAX_DOWNLOAD_MB = int(
    os.getenv(
        "MAX_DOWNLOAD_MB",
        "25",
    )
)

MAX_UPLOAD_BYTES = (
    MAX_UPLOAD_MB * 1024 * 1024
)

MAX_DOWNLOAD_BYTES = (
    MAX_DOWNLOAD_MB * 1024 * 1024
)


# Semantic retrieval configuration
RETRIEVAL_TOP_K = int(
    os.getenv(
        "RETRIEVAL_TOP_K",
        "12",
    )
)

RETRIEVAL_FINAL_K = int(
    os.getenv(
        "RETRIEVAL_FINAL_K",
        "6",
    )
)

RETRIEVAL_MIN_SCORE = float(
    os.getenv(
        "RETRIEVAL_MIN_SCORE",
        "0.10",
    )
)


# Frontend CORS configuration
CORS_ORIGINS = [
    value.strip()
    for value in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173,http://localhost:4174,http://127.0.0.1:4174,http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if value.strip()
]


# API rate limiting
RATE_LIMIT_WINDOW = int(
    os.getenv(
        "RATE_LIMIT_WINDOW",
        "60",
    )
)

RATE_LIMIT_REQUESTS = int(
    os.getenv(
        "RATE_LIMIT_REQUESTS",
        "60",
    )
)


# Permitted hosts for supported external paper URLs
ALLOWED_URL_HOSTS = {
    "arxiv.org",
    "export.arxiv.org",
    "doi.org",
    "dx.doi.org",
}


# Create required data directories
for directory in (
    DATA_DIR,
    STORAGE_DIR,
    PDF_DIR,
    REPORT_DIR,
    CHART_DIR,
    CHROMA_DIR,
):
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )
