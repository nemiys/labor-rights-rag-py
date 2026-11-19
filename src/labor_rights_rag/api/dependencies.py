"""Things the endpoints get injected: tests replace them with fakes."""

import asyncio
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.embeddings.base import Embedder
from labor_rights_rag.embeddings.factory import make_embedder
from labor_rights_rag.generation.base import Answerer
from labor_rights_rag.generation.factory import make_answerer
from labor_rights_rag.persistence.database import get_session
from labor_rights_rag.retrieval.bm25 import Bm25Index, load_bm25_index
from labor_rights_rag.settings import settings

# Two requests arriving together must not both build the index.
_bm25_lock = asyncio.Lock()


@lru_cache
def get_embedder() -> Embedder:
    """One model for the whole process: loading it takes a while and about 2 GB of memory."""
    return make_embedder(settings.embedder)


@lru_cache
def get_answerer() -> Answerer:
    return make_answerer(settings.answerer)


SessionDep = Annotated[AsyncSession, Depends(get_session)]


Bm25Loader = Callable[[], Awaitable[Bm25Index]]


def get_bm25(request: Request, session: SessionDep) -> Bm25Loader:
    """A way to get the word index, not the index itself: only the modes of /search that
    need it call the loader, so a vector search (and /ask) never builds it. Built from the
    chunks on the first call and then kept; not refreshed while the application runs, so
    restart it after an ingest."""

    async def load() -> Bm25Index:
        index: Bm25Index | None = getattr(request.app.state, "bm25", None)
        if index is None:
            async with _bm25_lock:
                index = getattr(request.app.state, "bm25", None)
                if index is None:
                    index = await load_bm25_index(session)
                    request.app.state.bm25 = index
        return index

    return load


EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
AnswererDep = Annotated[Answerer, Depends(get_answerer)]
Bm25Dep = Annotated[Bm25Loader, Depends(get_bm25)]
