import asyncio
import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope

from labor_rights_rag.api import ask, laws, search
from labor_rights_rag.api.dependencies import get_embedder
from labor_rights_rag.api.rate_limit import SlidingWindowLimiter
from labor_rights_rag.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Load the model at start-up: a bad setup fails now, not on the first question.
    # The BM25 index is not built here: only the debug modes of /search use it, so it is
    # built the first time one of them is asked for (see api/dependencies.py).
    await asyncio.to_thread(get_embedder)
    yield


WEB = Path(__file__).parent / "web"
ASSETS = ("style.css", "app.js")
# The page loads only its own files and talks only to its own server. No inline scripts.
PAGE_POLICY = (
    "default-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)


class RevalidatedStaticFiles(StaticFiles):
    """Static files that the browser must check with the server on every load.

    Without a caching rule a browser guesses how long a file stays fresh, and may keep an old
    script while it shows the new page. The check is cheap: the answer is "not modified".
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


def page_with_versioned_assets() -> str:
    """The page, with each file's address carrying a version taken from its content.

    The page itself is fetched on every visit, so a changed script gets a new address and is
    downloaded even by a browser that still holds the old one.
    """
    page = (WEB / "index.html").read_text(encoding="utf-8")
    for name in ASSETS:
        version = hashlib.sha256((WEB / name).read_bytes()).hexdigest()[:10]
        page = page.replace(f"/static/{name}", f"/static/{name}?v={version}")
    return page


def create_app() -> FastAPI:
    app = FastAPI(title="labor-rights-rag", lifespan=lifespan)
    app.state.ask_limiter = SlidingWindowLimiter(settings.ask_limit, settings.ask_window_seconds)
    app.include_router(search.router)
    app.include_router(ask.router)
    app.include_router(laws.router)
    app.mount("/static", RevalidatedStaticFiles(directory=WEB), name="static")

    # Built once per process: the files only change with a new deployment.
    page = page_with_versioned_assets()

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def home() -> HTMLResponse:
        return HTMLResponse(
            page,
            headers={"Content-Security-Policy": PAGE_POLICY, "Cache-Control": "no-cache"},
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
