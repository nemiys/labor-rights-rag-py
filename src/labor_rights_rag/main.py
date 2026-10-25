import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from labor_rights_rag.api import ask, search
from labor_rights_rag.api.dependencies import get_embedder


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Load the model at start-up: a bad setup fails now, not on the first question.
    await asyncio.to_thread(get_embedder)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="labor-rights-rag", lifespan=lifespan)
    app.include_router(search.router)
    app.include_router(ask.router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
