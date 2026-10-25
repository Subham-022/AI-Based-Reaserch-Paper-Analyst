from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import (
    FastAPI,
    Request,
)
from fastapi.middleware.cors import (
    CORSMiddleware,
)
from fastapi.responses import JSONResponse

from app.api import chat, compare, papers, reports
from app.config import (
    CORS_ORIGINS,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW,
)
from app.db import init_db


app = FastAPI(
    title="AI Based Research Paper Analyst",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_request_times: dict[
    str,
    deque[float],
] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(
    request: Request,
    call_next,
):
    client = request.client

    if client is None:
        key = "unknown"
    else:
        key = client.host

    now = time.monotonic()
    timestamps = _request_times[key]

    while timestamps:
        if now - timestamps[0] <= RATE_LIMIT_WINDOW:
            break

        timestamps.popleft()

    if len(timestamps) >= RATE_LIMIT_REQUESTS:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": (
                        "Too many requests. "
                        "Please try again shortly."
                    ),
                }
            },
        )

    timestamps.append(now)

    return await call_next(request)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
    }


@app.get("/")
def root() -> dict:
    return {
        "name": (
            "AI Based Research Paper Analyst"
        ),
        "status": "running",
    }


app.include_router(
    papers.router,
    prefix="/api",
)

app.include_router(
    chat.router,
    prefix="/api",
)

app.include_router(
    compare.router,
    prefix="/api",
)

app.include_router(
    reports.router,
    prefix="/api",
)