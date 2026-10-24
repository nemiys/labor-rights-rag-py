"""A deterministic stand-in for tests: no model, no download.

Each word is hashed to a position of the vector, so two texts that share words are
close and two texts that share none are not. It understands no meaning, which is fine
for testing the plumbing (storing, searching, ordering).
"""

import hashlib
import math
import re
from collections.abc import Sequence

from labor_rights_rag.embeddings.base import EMBEDDING_DIM

_WORD = re.compile(r"\w+")


class HashEmbedder:
    name = "hash-fake"

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for word in _WORD.findall(text):
            digest = hashlib.sha256(word.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dim] += 1.0
        length = math.sqrt(sum(value * value for value in vector))
        return [value / length for value in vector] if length else vector
