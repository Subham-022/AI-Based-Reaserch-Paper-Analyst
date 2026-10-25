from typing import Any

import app.retrieval.search as search_module
from app.retrieval.search import (
    Retriever,
)


class FakeEmbedder:
    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return [
            [1.0, 0.0]
            for _ in texts
        ]


class FakeStore:
    def search(
        self,
        embedding: list[float],
        top_k: int = 12,
        paper_ids: list[str] | None = None,
        section: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [
            {
                "text": (
                    "The proposed method uses "
                    "a transformer architecture."
                ),
                "metadata": {
                    "paper_id": "paper-1",
                    "chunk_id": "paper-1:1",
                    "section": "methods",
                    "page": 4,
                },
                "distance": 0.05,
                "score": 0.95,
            },
            {
                "text": (
                    "The reported accuracy "
                    "was 91 percent."
                ),
                "metadata": {
                    "paper_id": "paper-2",
                    "chunk_id": "paper-2:1",
                    "section": "results",
                    "page": 7,
                },
                "distance": 0.90,
                "score": 0.10,
            },
        ]

        filtered = []

        for row in rows:
            metadata = row["metadata"]

            if (
                paper_ids
                and metadata["paper_id"]
                not in paper_ids
            ):
                continue

            if (
                section
                and metadata["section"]
                != section
            ):
                continue

            filtered.append(row)

        return filtered[:top_k]


def test_retrieval_returns_citation() -> None:
    retriever = Retriever(
        store=FakeStore(),
        embedder=FakeEmbedder(),
        confidence_threshold=0.25,
    )

    results = retriever.search(
        query="What method was used?",
        paper_ids=["paper-1"],
        section="methods",
    )

    assert len(results) == 1

    citation = results[0]

    assert citation.paper_id == (
        "paper-1"
    )

    assert citation.chunk_id == (
        "paper-1:1"
    )

    assert citation.section == (
        "methods"
    )

    assert citation.page == 4

    assert citation.score == 0.95


def test_retrieval_discards_low_confidence_results() -> None:
    retriever = Retriever(
        store=FakeStore(),
        embedder=FakeEmbedder(),
        confidence_threshold=0.25,
    )

    results = retriever.search(
        query="What is the result?"
    )

    assert len(results) == 1

    assert results[0].paper_id == (
        "paper-1"
    )


def test_configured_search_uses_persistent_retriever(
    monkeypatch,
) -> None:
    embedder_count = 0
    store_count = 0

    class ConfiguredEmbedder(FakeEmbedder):
        def __init__(self, model_name: str) -> None:
            nonlocal embedder_count
            embedder_count += 1
            assert model_name

    def configured_store(path):
        nonlocal store_count
        store_count += 1
        return FakeStore()

    monkeypatch.setattr(
        search_module,
        "Embedder",
        ConfiguredEmbedder,
    )
    monkeypatch.setattr(
        search_module,
        "VectorStore",
        configured_store,
    )

    search_module._get_configured_retriever.cache_clear()
    try:
        results = search_module.search(
            query="What method was used?",
            paper_ids=["paper-1"],
            section="methods",
            top_k=3,
        )
        search_module.search(
            query="What result was reported?",
            paper_ids=["paper-1"],
        )
    finally:
        search_module._get_configured_retriever.cache_clear()

    assert len(results) == 1
    assert results[0].paper_id == "paper-1"
    assert results[0].section == "methods"
    assert embedder_count == 1
    assert store_count == 1