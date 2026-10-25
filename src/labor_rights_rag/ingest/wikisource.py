"""Client for the Open Law Book on Hebrew Wikisource, through the MediaWiki API."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class WikisourcePage:
    title: str
    revid: int  # changes on every edit: if it did not change, the page did not either
    wikitext: str


class WikisourceError(Exception):
    pass


class WikisourceClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        retry_delays: Sequence[float] = (2.0, 5.0),
    ) -> None:
        self._client = client
        self._api_url = api_url
        # The site sometimes drops a connection for no reason; a short wait and a new try
        # are enough. One delay per retry.
        self._retry_delays = retry_delays

    async def _get(self, params: dict[str, str]) -> httpx.Response:
        for delay in (*self._retry_delays, None):
            try:
                response = await self._client.get(self._api_url, params=params)
                if response.status_code not in (429, 500, 502, 503, 504):
                    return response
                error: Exception = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}", request=response.request, response=response
                )
            except httpx.TransportError as transport_error:
                error = transport_error
            if delay is None:
                raise error
            await asyncio.sleep(delay)
        raise AssertionError("unreachable")  # the loop above always returns or raises

    async def get_page(self, title: str) -> WikisourcePage | None:
        params = {
            "action": "query",
            "titles": title,
            "prop": "revisions",
            "rvprop": "ids|content",
            "rvslots": "main",
            "redirects": "1",
            "format": "json",
            "formatversion": "2",
            # Ask the API to refuse when its databases lag, instead of adding load.
            "maxlag": "5",
        }
        response = await self._get(params)
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            raise WikisourceError(f"{title}: {body['error'].get('code')}")
        page = body["query"]["pages"][0]
        if page.get("missing") or "revisions" not in page:
            return None
        revision = page["revisions"][0]
        return WikisourcePage(
            page["title"], revision["revid"], revision["slots"]["main"]["content"]
        )
