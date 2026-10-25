import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from labor_rights_rag.api import ask, laws, search
from labor_rights_rag.api.dependencies import get_embedder
from labor_rights_rag.persistence.database import session_factory
from labor_rights_rag.retrieval.bm25 import load_bm25_index


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Load the model at start-up: a bad setup fails now, not on the first question.
    await asyncio.to_thread(get_embedder)
    # The BM25 index is a few hundred kilobytes in memory. It is not refreshed while the
    # application runs: restart it after an ingest.
    async with session_factory() as session:
        app.state.bm25 = await load_bm25_index(session)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="labor-rights-rag", lifespan=lifespan)
    app.include_router(search.router)
    app.include_router(ask.router)
    app.include_router(laws.router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
