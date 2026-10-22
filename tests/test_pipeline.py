from datetime import UTC, date, datetime
from pathlib import Path

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.ingest.corpus import CorpusLaw
from labor_rights_rag.ingest.knesset import AmbiguousLawError, KnessetLaw
from labor_rights_rag.ingest.pipeline import LawResult, collect, save_law
from labor_rights_rag.ingest.report import format_report
from labor_rights_rag.ingest.wikisource import WikisourcePage
from labor_rights_rag.parsing.wikitext import parse_law
from labor_rights_rag.persistence.models import Law

WIKITEXT = (Path(__file__).parent / "fixtures" / "wikisource" / "annual_leave.wiki").read_text(
    encoding="utf-8"
)
LAW = CorpusLaw("חוק חופשה שנתית", "חוק חופשה שנתית")
KNESSET = KnessetLaw(2000658, 'חוק חופשה שנתית, התשי"א-1951', None, date(2026, 7, 20), "תקף")


class FakeRegistry:
    def __init__(self, law: KnessetLaw | None = KNESSET, ambiguous: bool = False) -> None:
        self.law = law
        self.ambiguous = ambiguous

    async def find_law(self, title: str) -> KnessetLaw | None:
        if self.ambiguous:
            raise AmbiguousLawError(title)
        return self.law


class FakePages:
    def __init__(self, wikitext: str | None = WIKITEXT, revid: int = 3037796) -> None:
        self.wikitext = wikitext
        self.revid = revid

    async def get_page(self, title: str) -> WikisourcePage | None:
        return None if self.wikitext is None else WikisourcePage(title, self.revid, self.wikitext)


async def test_law_found_in_both_sources_is_storable_and_current() -> None:
    result = await collect(LAW, FakeRegistry(), FakePages())

    assert result.storable
    assert result.status == "ok"
    assert result.issues == []


async def test_law_missing_from_the_registry_is_not_stored() -> None:
    result = await collect(LAW, FakeRegistry(law=None), FakePages())

    assert not result.storable
    assert "not found in the Knesset registry" in result.issues


async def test_ambiguous_registry_match_is_not_stored() -> None:
    result = await collect(LAW, FakeRegistry(ambiguous=True), FakePages())

    assert not result.storable


async def test_missing_page_is_not_stored() -> None:
    result = await collect(LAW, FakeRegistry(), FakePages(wikitext=None))

    assert "page not found in the Open Law Book" in result.issues


class FailingPages:
    async def get_page(self, title: str) -> WikisourcePage | None:
        raise httpx.ConnectTimeout("timed out")


async def test_network_error_for_one_law_is_recorded_not_raised() -> None:
    result = await collect(LAW, FakeRegistry(), FailingPages())

    assert not result.storable
    assert any("request failed" in issue for issue in result.issues)


async def test_page_pointing_to_another_knesset_id_is_not_stored() -> None:
    other = KnessetLaw(1, "חוק אחר, התש״י-1950", None, date(2026, 7, 20), "תקף")

    result = await collect(LAW, FakeRegistry(law=other), FakePages())

    assert any("Knesset id mismatch" in issue for issue in result.issues)


async def test_repealed_law_is_stored_with_a_warning() -> None:
    repealed = KnessetLaw(2000658, KNESSET.name, None, date(2026, 7, 20), "בטל")

    result = await collect(LAW, FakeRegistry(law=repealed), FakePages())

    assert result.storable
    assert result.warnings == ["validity: בטל"]


def _stored_result(revid: int) -> LawResult:
    # An id that no real law has: the development database may already hold the real ones.
    knesset = KnessetLaw(999002, "חוק לבדיקה, התשפ״ו-2026", None, date(2026, 7, 20), "תקף")
    page = WikisourcePage("חוק לבדיקה", revid, WIKITEXT)
    return LawResult(LAW, knesset, page, parse_law(WIKITEXT), status="ok")


async def test_saving_twice_updates_one_row(db_session: AsyncSession) -> None:
    first, second, third = _stored_result(1), _stored_result(2), _stored_result(2)
    now = datetime.now(UTC)

    for result in (first, second, third):
        await save_law(db_session, result, now)

    count = await db_session.scalar(select(func.count()).where(Law.odata_id == 999002))
    law = (await db_session.execute(select(Law).where(Law.odata_id == 999002))).scalar_one()
    assert count == 1
    assert [first.change, second.change, third.change] == ["new", "changed", "unchanged"]
    assert law.revid == 2
    assert law.last_amendment_year == 5786
    assert law.last_amendment_url and law.last_amendment_url.endswith(".pdf")


def test_report_lists_every_law_and_its_status() -> None:
    stored = LawResult(LAW, KNESSET, status="ok")
    missing = LawResult(CorpusLaw("חוק ב", "חוק ב"), issues=["not found in the Knesset registry"])

    report = format_report([stored, missing])

    assert "Laws in corpus: 2." in report
    assert "| חוק ב | - |" in report
    assert "not found in the Knesset registry" in report
