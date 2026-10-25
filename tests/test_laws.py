from collections.abc import AsyncIterator
from datetime import UTC, date, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.generation.messages import CURRENCY_WARNINGS
from labor_rights_rag.main import create_app
from labor_rights_rag.persistence.database import get_session
from labor_rights_rag.persistence.models import Law

# Ids that no real law has: the development database may already hold the real ones.
CURRENT, AHEAD, BARE = 999016, 999017, 999018


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    db_session.add_all(
        [
            Law(
                odata_id=CURRENT,
                name="חוק א לבדיקה",
                wikisource_title="חוק א לבדיקה",
                validity="תקף",
                last_publication_date=date(2024, 6, 4),
                last_amendment_year=5786,
                last_amendment_label="תיקון מס׳ 9",
                last_amendment_url="https://example.org/9.pdf",
                currency_status="ok",
                fetched_at=datetime(2026, 10, 22, 9, 0, tzinfo=UTC),
            ),
            Law(
                odata_id=AHEAD,
                name="חוק ב לבדיקה",
                wikisource_title="חוק ב לבדיקה",
                currency_status="ahead",
            ),
            Law(odata_id=BARE, name="חוק ג לבדיקה", wikisource_title="חוק ג לבדיקה"),
        ]
    )
    await db_session.flush()
    app = create_app()

    async def session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


async def _by_id(client: AsyncClient) -> dict[int, dict[str, object]]:
    response = await client.get("/laws")
    assert response.status_code == 200
    return {law["id"]: law for law in response.json()}


async def test_a_law_comes_with_its_dates_links_and_amendment(client: AsyncClient) -> None:
    law = (await _by_id(client))[CURRENT]

    assert law["name"] == "חוק א לבדיקה"
    assert law["validity"] == "תקף"
    assert law["last_publication_date"] == "2024-06-04"
    assert law["last_amendment"] == "5786 (2025-26)"
    assert law["last_amendment_url"] == "https://example.org/9.pdf"
    assert law["text_as_of"] == "2026-10-22"
    assert str(law["knesset_url"]).endswith(f"lawitemid={CURRENT}")
    assert str(law["wikisource_url"]).startswith("https://he.wikisource.org/wiki/")


async def test_a_current_law_has_no_warning_and_a_lagging_one_has(client: AsyncClient) -> None:
    laws = await _by_id(client)

    assert laws[CURRENT]["currency_warning"] is None
    assert laws[AHEAD]["currency_warning"] == CURRENCY_WARNINGS["ahead"]


async def test_a_law_with_missing_data_is_listed_without_it(client: AsyncClient) -> None:
    law = (await _by_id(client))[BARE]

    assert law["currency_status"] == "unknown"
    assert law["currency_warning"] == CURRENCY_WARNINGS["unknown"]
    assert law["last_amendment"] is None
    assert law["text_as_of"] is None


async def test_laws_are_sorted_by_name(client: AsyncClient) -> None:
    names = [law["name"] for law in (await client.get("/laws")).json()]

    assert names == sorted(names)
