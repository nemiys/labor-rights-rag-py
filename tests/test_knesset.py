from datetime import date

import httpx
import pytest
import respx

from labor_rights_rag.ingest.knesset import (
    AmbiguousLawError,
    KnessetClient,
    KnessetLaw,
    pick_law,
)

BASE = "https://odata.example/ParliamentInfo"


def _law(name: str, validity: str = "תקף", odata_id: int = 1) -> KnessetLaw:
    return KnessetLaw(odata_id, name, None, None, validity)


def _record(odata_id: int, name: str, validity: str = "תקף") -> dict[str, object]:
    return {
        "Id": odata_id,
        "Name": name,
        "PublicationDate": "1951-05-22T00:00:00+03:00",
        "LatestPublicationDate": "2018-06-21T00:00:00+03:00",
        "LawValidityDesc": validity,
    }


def test_title_matches_the_name_with_its_year_suffix() -> None:
    law = _law('חוק דמי מחלה, התשל"ו-1976')

    assert pick_law("חוק דמי מחלה", [law]) == law


def test_a_longer_name_with_a_parenthesis_is_a_different_law() -> None:
    other = _law('חוק דמי מחלה (היעדרות בשל מחלת ילד), התשנ"ג-1993')

    assert pick_law("חוק דמי מחלה", [other]) is None


def test_valid_law_is_preferred_over_a_repealed_one() -> None:
    repealed = _law('חוק א, התש"י-1950', validity="בטל", odata_id=1)
    valid = _law('חוק א, התשכ"ה-1965', odata_id=2)

    assert pick_law("חוק א", [repealed, valid]) == valid


def test_two_valid_matches_are_ambiguous() -> None:
    laws = [_law('חוק א, התש"י-1950', odata_id=1), _law('חוק א, התשכ"ה-1965', odata_id=2)]

    with pytest.raises(AmbiguousLawError):
        pick_law("חוק א", laws)


def test_no_match_returns_none() -> None:
    assert pick_law("חוק ב", [_law('חוק א, התש"י-1950')]) is None


@respx.mock
async def test_filter_encodes_spaces_as_percent20_not_plus() -> None:
    # Regression: with "+" the service matched nothing and the law looked missing.
    route = respx.get(url__startswith=f"{BASE}/KNS_IsraelLaw").respond(json={"value": []})

    async with httpx.AsyncClient() as client:
        await KnessetClient(client, BASE).find_law("חוק חופשה שנתית")

    url = str(route.calls.last.request.url)
    assert "%20" in url
    assert "+" not in url


@respx.mock
async def test_follows_next_link_and_parses_the_record() -> None:
    next_url = f"{BASE}/KNS_IsraelLaw?page=2"
    respx.get(url__startswith=f"{BASE}/KNS_IsraelLaw?$filter").respond(
        json={"value": [], "@odata.nextLink": next_url}
    )
    respx.get(next_url).respond(
        json={"value": [_record(2000019, 'חוק שעות עבודה ומנוחה, התשי"א-1951')]}
    )

    async with httpx.AsyncClient() as client:
        law = await KnessetClient(client, BASE).find_law("חוק שעות עבודה ומנוחה")

    assert law == KnessetLaw(
        odata_id=2000019,
        name='חוק שעות עבודה ומנוחה, התשי"א-1951',
        publication_date=date(1951, 5, 22),
        latest_publication_date=date(2018, 6, 21),
        validity="תקף",
    )
