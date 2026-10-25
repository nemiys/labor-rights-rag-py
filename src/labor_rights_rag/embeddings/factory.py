"""Chooses the embedding model by name: one place, shared by the ingest command and the API."""

from labor_rights_rag.embeddings.base import Embedder
from labor_rights_rag.embeddings.fake import HashEmbedder

EMBEDDER_NAMES = ("bge-m3", "hash")


def make_embedder(name: str) -> Embedder:
    if name == "hash":
        return HashEmbedder()
    if name == "bge-m3":
        # Imported here: it loads torch, which only this model needs.
        from labor_rights_rag.embeddings.bge_m3 import BgeM3Embedder

        return BgeM3Embedder()
    raise ValueError(f"unknown embedder: {name}")
