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


@respx.mock
async def test_a_dropped_connection_is_retried() -> None:
    route = respx.get(API).mock(
        side_effect=[
            httpx.ReadError("dropped"),
            httpx.Response(503),
            httpx.Response(200, json=_page_body("חוק א", 7, "טקסט")),
        ]
    )

    async with httpx.AsyncClient() as client:
        page = await WikisourceClient(client, API, retry_delays=(0, 0)).get_page("חוק א")

    assert page is not None
    assert page.revid == 7
    assert route.call_count == 3


@respx.mock
async def test_the_error_is_raised_when_every_try_fails() -> None:
    route = respx.get(API).mock(side_effect=httpx.ReadError("dropped"))

    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.ReadError):
            await WikisourceClient(client, API, retry_delays=(0, 0)).get_page("חוק א")

    assert route.call_count == 3


@respx.mock
async def test_a_missing_page_is_not_retried() -> None:
    route = respx.get(API).respond(json={"query": {"pages": [{"title": "חוק ב", "missing": True}]}})

    async with httpx.AsyncClient() as client:
        assert await WikisourceClient(client, API, retry_delays=(0, 0)).get_page("חוק ב") is None

    assert route.call_count == 1
