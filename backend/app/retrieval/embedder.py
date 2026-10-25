from __future__ import annotations

from typing import Any


DEFAULT_MODEL = (
    "sentence-transformers/"
    "all-MiniLM-L6-v2"
)


class Embedder:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
    ) -> None:
        self.model_name = model_name
        self._model: Any | None = None

    @property
    def model(self) -> Any:
        if self._model is None:
            from sentence_transformers import (
                SentenceTransformer,
            )

            self._model = SentenceTransformer(
                self.model_name
            )

        return self._model

    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        if not texts:
            return []

        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        return vectors.tolist()