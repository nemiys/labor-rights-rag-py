"""Client for the Open Law Book on Hebrew Wikisource, through the MediaWiki API."""

from collections.abc import Sequence
from dataclasses import dataclass

import httpx

from labor_rights_rag.http_retry import with_retries


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
        response = await with_retries(
            lambda: self._client.get(self._api_url, params=params), self._retry_delays
        )
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
