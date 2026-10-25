from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ingestion.sectioner import Chunk


COLLECTION_NAME = "paper_chunks"


class VectorStore:
    def __init__(
        self,
        path: Path,
    ) -> None:
        path.mkdir(
            parents=True,
            exist_ok=True,
        )

        import chromadb

        self.client = (
            chromadb.PersistentClient(
                path=str(path)
            )
        )

        self.collection = (
            self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={
                    "hnsw:space": "cosine",
                },
            )
        )

        print("CHROMA COLLECTION READY")

    def add(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        if not chunks:
            return

        if len(chunks) != len(embeddings):
            raise ValueError(
                "The number of chunks must match "
                "the number of embeddings."
            )

        print(
            f"CHROMA UPSERT START: "
            f"{len(chunks)} chunks"
        )

        self.collection.upsert(
            ids=[
                chunk.id
                for chunk in chunks
            ],
            documents=[
                chunk.text
                for chunk in chunks
            ],
            embeddings=embeddings,
            metadatas=[
                {
                    "paper_id": chunk.paper_id,
                    "section": chunk.section,
                    "page": chunk.page,
                    "chunk_id": chunk.id,
                    "content_type": (
                        chunk.content_type
                    ),
                    "content_hash": (
                        chunk.content_hash
                    ),
                }
                for chunk in chunks
            ],
        )

        print("CHROMA UPSERT COMPLETE")

    def search(
        self,
        embedding: list[float],
        top_k: int = 12,
        paper_ids: list[str] | None = None,
        section: str | None = None,
    ) -> list[dict[str, Any]]:
        where: dict[str, Any] | None = None

        if paper_ids:
            if len(paper_ids) == 1:
                where = {
                    "paper_id": paper_ids[0]
                }
            else:
                where = {
                    "paper_id": {
                        "$in": paper_ids
                    }
                }

        if section:
            section_filter = {
                "section": section
            }

            if where is None:
                where = section_filter
            else:
                where = {
                    "$and": [
                        where,
                        section_filter,
                    ]
                }

        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        documents = result.get(
            "documents",
            [[]],
        )[0]

        metadatas = result.get(
            "metadatas",
            [[]],
        )[0]

        distances = result.get(
            "distances",
            [[]],
        )[0]

        rows: list[
            dict[str, Any]
        ] = []

        for (
            document,
            metadata,
            distance,
        ) in zip(
            documents,
            metadatas,
            distances,
        ):
            score = 1.0 - float(
                distance
            )

            rows.append(
                {
                    "text": document,
                    "metadata": metadata,
                    "distance": float(
                        distance
                    ),
                    "score": score,
                }
            )

        return rows

    def delete_paper(
        self,
        paper_id: str,
    ) -> None:
        self.collection.delete(
            where={
                "paper_id": paper_id
            }
        )

    def count(self) -> int:
        return self.collection.count()