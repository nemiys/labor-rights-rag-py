"""Things the endpoints get injected: tests replace them with fakes."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.embeddings.base import Embedder
from labor_rights_rag.embeddings.factory import make_embedder
from labor_rights_rag.generation.base import Answerer
from labor_rights_rag.generation.factory import make_answerer
from labor_rights_rag.persistence.database import get_session
from labor_rights_rag.retrieval.bm25 import Bm25Index
from labor_rights_rag.settings import settings


@lru_cache
def get_embedder() -> Embedder:
    """One model for the whole process: loading it takes a while and about 2 GB of memory."""
    return make_embedder(settings.embedder)


@lru_cache
def get_answerer() -> Answerer:
    return make_answerer(settings.answerer)


def get_bm25(request: Request) -> Bm25Index | None:
    """The word index, built when the application started (see main.py); None if it was not."""
    index: Bm25Index | None = getattr(request.app.state, "bm25", None)
    return index


SessionDep = Annotated[AsyncSession, Depends(get_session)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
AnswererDep = Annotated[Answerer, Depends(get_answerer)]
Bm25Dep = Annotated[Bm25Index | None, Depends(get_bm25)]
