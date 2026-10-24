"""Fetch one law from both sources, check it, and store its row in `laws`.

Sections are parsed here only to check the page and to report on it. They are
stored as chunks in stage 3, once the chunking rules are decided.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.ingest.corpus import CorpusLaw
from labor_rights_rag.ingest.currency import UNKNOWN, currency_status
from labor_rights_rag.ingest.knesset import VALID, AmbiguousLawError, KnessetLaw
from labor_rights_rag.ingest.wikisource import WikisourceError, WikisourcePage
from labor_rights_rag.parsing.wikitext import ParsedLaw, parse_law
from labor_rights_rag.persistence.models import Law


class LawRegistry(Protocol):
    async def find_law(self, title: str) -> KnessetLaw | None: ...


class PageSource(Protocol):
    async def get_page(self, title: str) -> WikisourcePage | None: ...


@dataclass
class IndexStats:
    """What indexing did to the chunks of one law."""

    added: int = 0  # new chunks
    kept: int = 0  # unchanged, already embedded by the current model: not touched
    removed: int = 0  # no longer in the law
    embedded: int = 0  # vectors computed in this run


@dataclass
class LawResult:
    corpus: CorpusLaw
    knesset: KnessetLaw | None = None
    page: WikisourcePage | None = None
    parsed: ParsedLaw | None = None
    status: str = UNKNOWN
    issues: list[str] = field(default_factory=list)  # problems that block storing the law
    warnings: list[str] = field(default_factory=list)  # stored, but worth a look
    change: str = ""  # "new", "changed" or "unchanged", filled in when saved
    index: IndexStats | None = None  # filled in when the chunks are indexed

    @property
    def storable(self) -> bool:
        return not self.issues and None not in (self.knesset, self.page, self.parsed)


async def collect(law: CorpusLaw, registry: LawRegistry, pages: PageSource) -> LawResult:
    """Never raises for one law's problem: it is recorded, and the run goes on."""
    result = LawResult(law)
    try:
        result.knesset = await registry.find_law(law.title)
    except AmbiguousLawError as error:
        result.issues.append(f"ambiguous in the Knesset registry: {error}")
    except httpx.HTTPError as error:
        result.issues.append(f"Knesset registry request failed: {error!r}")
    if result.knesset is None and not result.issues:
        result.issues.append("not found in the Knesset registry")

    try:
        result.page = await pages.get_page(law.wikisource_title)
    except (httpx.HTTPError, WikisourceError) as error:
        result.issues.append(f"Open Law Book request failed: {error!r}")
        return result
    if result.page is None:
        result.issues.append("page not found in the Open Law Book")
        return result

    result.parsed = parse_law(result.page.wikitext)
    if not result.parsed.sections:
        result.issues.append("no sections parsed")

    if result.knesset is not None:
        # The page names its Knesset id; it must be the law we found by name.
        if result.parsed.knesset_id != result.knesset.odata_id:
            result.issues.append(
                f"Knesset id mismatch: page {result.parsed.knesset_id}, "
                f"registry {result.knesset.odata_id}"
            )
        if result.knesset.validity != VALID:
            result.warnings.append(f"validity: {result.knesset.validity}")
        result.status = currency_status(
            result.parsed.last_amendment_year, result.knesset.latest_publication_date
        )
    return result


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def save_law(session: AsyncSession, result: LawResult, fetched_at: datetime) -> None:
    """Insert or update the law's row, keyed by its Knesset id: running twice is safe."""
    assert result.knesset and result.page and result.parsed
    last = result.parsed.amendments[-1] if result.parsed.amendments else None
    values = {
        "odata_id": result.knesset.odata_id,
        "name": result.knesset.name,
        "wikisource_title": result.page.title,
        "validity": result.knesset.validity,
        "last_publication_date": result.knesset.latest_publication_date,
        "last_amendment_year": result.parsed.last_amendment_year,
        "last_amendment_label": last.label if last else None,
        "last_amendment_url": last.url if last else None,
        "revid": result.page.revid,
        "content_hash": content_hash(result.page.wikitext),
        "currency_status": result.status,
        "fetched_at": fetched_at,
    }

    stored = (
        await session.execute(select(Law.revid).where(Law.odata_id == result.knesset.odata_id))
    ).first()
    if stored is None:
        result.change = "new"
    else:
        result.change = "unchanged" if stored.revid == result.page.revid else "changed"

    statement = insert(Law).values(**values)
    statement = statement.on_conflict_do_update(
        index_elements=[Law.odata_id],
        set_={key: statement.excluded[key] for key in values if key != "odata_id"},
    )
    await session.execute(statement)
