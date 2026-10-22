"""Client for the Knesset OData registry (KNS_IsraelLaw): official metadata about each law.

It holds validity and publication dates, not the law's text.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import quote

import httpx

VALID = "תקף"
_FIELDS = "Id,Name,PublicationDate,LatestPublicationDate,LawValidityDesc"


@dataclass(frozen=True)
class KnessetLaw:
    odata_id: int
    name: str
    publication_date: date | None
    latest_publication_date: date | None
    validity: str | None


class AmbiguousLawError(Exception):
    """More than one valid law in the registry matches the title."""


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value[:10]) if value else None


def _parse_law(record: dict[str, Any]) -> KnessetLaw:
    return KnessetLaw(
        odata_id=record["Id"],
        name=record["Name"],
        publication_date=_parse_date(record.get("PublicationDate")),
        latest_publication_date=_parse_date(record.get("LatestPublicationDate")),
        validity=record.get("LawValidityDesc"),
    )


def _filter_url(base_url: str, title: str) -> str:
    # Built by hand, not with httpx `params`: that encodes a space as "+", which OData
    # reads as a literal plus sign, so the filter silently matches nothing. quote() gives %20.
    literal = title.replace("'", "''")
    odata_filter = quote(f"startswith(Name,'{literal}')")
    return f"{base_url}/KNS_IsraelLaw?$filter={odata_filter}&$select={_FIELDS}&$top=100"


def pick_law(title: str, candidates: list[KnessetLaw]) -> KnessetLaw | None:
    """The registry names a law "<title>, <Hebrew year>-<year>"; a title that is only a
    prefix of a longer name (for example one with a parenthesis) is a different law."""
    matches = [c for c in candidates if c.name == title or c.name.startswith(f"{title},")]
    valid = [c for c in matches if c.validity == VALID]
    if len(valid) > 1:
        raise AmbiguousLawError(f"{title}: {[c.name for c in valid]}")
    if valid:
        return valid[0]
    return matches[0] if matches else None


class KnessetClient:
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def find_law(self, title: str) -> KnessetLaw | None:
        candidates: list[KnessetLaw] = []
        url: str | None = _filter_url(self._base_url, title)
        while url:  # the service returns pages; follow the links until there are none
            response = await self._client.get(url)
            response.raise_for_status()
            body = response.json()
            candidates.extend(_parse_law(record) for record in body["value"])
            url = body.get("@odata.nextLink")
        return pick_law(title, candidates)
