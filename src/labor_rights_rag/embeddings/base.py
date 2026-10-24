"""The interface of an embedding model: nothing outside `embeddings/` knows which one runs."""

from collections.abc import Sequence
from typing import Protocol

EMBEDDING_DIM = 1024  # BGE-M3, see docs/adr/0005-embedding-model.md


class Embedder(Protocol):
    name: str  # stored with every chunk: vectors of different models cannot be compared
    dim: int

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Vectors for the chunks being stored."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """The vector of a user's question. Kept apart because some models (e5) treat a
        question and a passage differently."""
        ...
