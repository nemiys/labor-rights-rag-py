"""Things the endpoints get injected: tests replace them with fakes."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.embeddings.base import Embedder
from labor_rights_rag.embeddings.factory import make_embedder
from labor_rights_rag.generation.base import Answerer
from labor_rights_rag.generation.factory import make_answerer
from labor_rights_rag.persistence.database import get_session
from labor_rights_rag.settings import settings


@lru_cache
def get_embedder() -> Embedder:
    """One model for the whole process: loading it takes a while and about 2 GB of memory."""
    return make_embedder(settings.embedder)


@lru_cache
def get_answerer() -> Answerer:
    return make_answerer(settings.answerer)


SessionDep = Annotated[AsyncSession, Depends(get_session)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
AnswererDep = Annotated[Answerer, Depends(get_answerer)]
