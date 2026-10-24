"""BGE-M3 through sentence-transformers. See docs/adr/0005-embedding-model.md.

Needs the optional extra: `uv sync --extra embeddings`. The first use downloads the
model (about 2 GB) into the Hugging Face cache, outside the project.
"""

from collections.abc import Sequence

from labor_rights_rag.embeddings.base import EMBEDDING_DIM


class BgeM3Embedder:
    name = "BAAI/bge-m3"
    dim = EMBEDDING_DIM

    def __init__(self, batch_size: int = 8, max_seq_length: int = 1024) -> None:
        try:
            # Imported here: it loads torch, which only this class needs.
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError("BGE-M3 needs the extra: uv sync --extra embeddings") from error
        self._model = SentenceTransformer(self.name)
        # Our chunks are far shorter than the model's limit; a lower cap bounds the memory.
        self._model.max_seq_length = max_seq_length
        actual = self._model.get_embedding_dimension()
        if actual != self.dim:
            raise ValueError(
                f"{self.name} gives {actual} dimensions, the schema expects {self.dim}"
            )
        self._batch_size = batch_size

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        # BGE-M3 needs no prefix: a question and a passage are encoded the same way.
        vectors = self._model.encode(
            list(texts),
            batch_size=self._batch_size,
            normalize_embeddings=True,  # unit length: cosine distance is then well defined
            show_progress_bar=False,
        )
        return [[float(value) for value in vector] for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
