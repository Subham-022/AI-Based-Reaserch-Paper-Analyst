from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.retrieval.embedder import Embedder
from app.retrieval.store import VectorStore


@dataclass(frozen=True)
class Citation:
    paper_id: str
    chunk_id: str
    section: str
    page: int
    text: str
    score: float


class Retriever:
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        confidence_threshold: float = 0.25,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.confidence_threshold = (
            confidence_threshold
        )

    def search(
        self,
        query: str,
        paper_ids: list[str] | None = None,
        section: str | None = None,
        top_k: int = 12,
    ) -> list[Citation]:
        query = query.strip()

        if not query:
            return []

        embeddings = self.embedder.embed(
            [query]
        )

        if not embeddings:
            return []

        rows = self.store.search(
            embedding=embeddings[0],
            top_k=top_k,
            paper_ids=paper_ids,
            section=section,
        )

        citations: list[Citation] = []
        seen_chunks: set[str] = set()

        for row in rows:
            score = float(
                row["score"]
            )

            if score < self.confidence_threshold:
                continue

            metadata = row["metadata"]

            chunk_id = str(
                metadata["chunk_id"]
            )

            if chunk_id in seen_chunks:
                continue

            seen_chunks.add(
                chunk_id
            )

            citations.append(
                Citation(
                    paper_id=str(
                        metadata["paper_id"]
                    ),
                    chunk_id=chunk_id,
                    section=str(
                        metadata["section"]
                    ),
                    page=int(
                        metadata["page"]
                    ),
                    text=str(
                        row["text"]
                    ),
                    score=score,
                )
            )

        return citations


@lru_cache(maxsize=1)
def _get_configured_retriever() -> Retriever:
    from app.config import (
        CHROMA_DIR,
        EMBEDDING_MODEL,
        RETRIEVAL_MIN_SCORE,
    )

    return Retriever(
        store=VectorStore(CHROMA_DIR),
        embedder=Embedder(model_name=EMBEDDING_MODEL),
        confidence_threshold=RETRIEVAL_MIN_SCORE,
    )


def get_retriever() -> Retriever:
    """Return the process-cached retriever for direct API use."""
    return _get_configured_retriever()


def search(
    query: str,
    paper_ids: list[str] | None = None,
    section: str | None = None,
    top_k: int = 12,
) -> list[Citation]:
    """Search the configured persistent index for cited passages."""
    return get_retriever().search(
        query=query,
        paper_ids=paper_ids,
        section=section,
        top_k=top_k,
    )