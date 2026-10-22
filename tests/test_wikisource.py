import httpx
import pytest
import respx

from labor_rights_rag.ingest.wikisource import WikisourceClient, WikisourceError, WikisourcePage

API = "https://wiki.example/w/api.php"


def _page_body(title: str, revid: int, content: str) -> dict[str, object]:
    revision = {"revid": revid, "slots": {"main": {"content": content}}}
    return {"query": {"pages": [{"title": title, "revisions": [revision]}]}}


@respx.mock
async def test_returns_title_revision_and_wikitext() -> None:
    route = respx.get(API).respond(json=_page_body("חוק א", 42, "{{ח:התחלה}}"))

    async with httpx.AsyncClient() as client:
        page = await WikisourceClient(client, API).get_page("חוק א")

    assert page == WikisourcePage("חוק א", 42, "{{ח:התחלה}}")
    assert route.calls.last.request.url.params["maxlag"] == "5"


@respx.mock
async def test_missing_page_returns_none() -> None:
    respx.get(API).respond(json={"query": {"pages": [{"title": "חוק ב", "missing": True}]}})

    async with httpx.AsyncClient() as client:
        assert await WikisourceClient(client, API).get_page("חוק ב") is None


@respx.mock
async def test_api_error_is_raised() -> None:
    respx.get(API).respond(json={"error": {"code": "maxlag"}})

    async with httpx.AsyncClient() as client:
        with pytest.raises(WikisourceError, match="maxlag"):
            await WikisourceClient(client, API).get_page("חוק א")
