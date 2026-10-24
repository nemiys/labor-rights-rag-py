from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.embeddings.fake import HashEmbedder
from labor_rights_rag.ingest.indexing import index_law
from labor_rights_rag.parsing.wikitext import Line, ParsedLaw, Section, parse_law
from labor_rights_rag.persistence.models import Chunk, Law

WIKITEXT = (Path(__file__).parent / "fixtures" / "wikisource" / "annual_leave.wiki").read_text(
    encoding="utf-8"
)


class CountingEmbedder(HashEmbedder):
    """The fake embedder that remembers how many texts it was asked to embed."""

    def __init__(self, name: str = "hash-fake") -> None:
        super().__init__()
        self.name = name
        self.seen = 0

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        self.seen += len(texts)
        return super().embed_documents(texts)


def _section(number: str, text: str) -> Section:
    return Section(number, f"כותרת {number}", None, [], [Line(2, True, f"(א) {text}")])


def _law_row() -> Law:
    # An id that no real law has: the development database may already hold the real ones.
    return Law(
        odata_id=999003,
        name="חוק לבדיקה, התשפ״ו-2026",
        wikisource_title="חוק לבדיקה",
        fetched_at=datetime.now(UTC),
    )


async def _count(session: AsyncSession, law: Law) -> int:
    return await session.scalar(select(func.count()).where(Chunk.law_id == law.id)) or 0


@pytest.fixture
async def law(db_session: AsyncSession) -> Law:
    row = _law_row()
    db_session.add(row)
    await db_session.flush()
    return row


async def test_first_run_stores_every_chunk_with_a_vector(
    db_session: AsyncSession, law: Law
) -> None:
    parsed = parse_law(WIKITEXT)
    embedder = CountingEmbedder()

    stats = await index_law(db_session, law, parsed, embedder)

    assert stats.added == await _count(db_session, law) > 0
    assert stats.embedded == stats.added == embedder.seen
    missing = await db_session.scalar(
        select(func.count()).where(Chunk.law_id == law.id, Chunk.embedding.is_(None))
    )
    assert missing == 0


async def test_second_run_computes_and_stores_nothing(db_session: AsyncSession, law: Law) -> None:
    parsed = parse_law(WIKITEXT)
    embedder = CountingEmbedder()
    first = await index_law(db_session, law, parsed, embedder)
    embedder.seen = 0

    second = await index_law(db_session, law, parsed, embedder)

    assert (second.added, second.removed, second.embedded) == (0, 0, 0)
    assert second.kept == first.added
    assert embedder.seen == 0
    assert await _count(db_session, law) == first.added


async def test_changed_section_is_the_only_one_recomputed(
    db_session: AsyncSession, law: Law
) -> None:
    embedder = CountingEmbedder()
    before = ParsedLaw(None, [_section("1", "ראשון"), _section("2", "שני")], [])
    after = ParsedLaw(None, [_section("1", "ראשון"), _section("2", "שני בנוסח חדש")], [])
    await index_law(db_session, law, before, embedder)
    embedder.seen = 0

    stats = await index_law(db_session, law, after, embedder)

    assert (stats.added, stats.removed, stats.kept, stats.embedded) == (1, 1, 1, 1)
    assert embedder.seen == 1
    texts = (await db_session.scalars(select(Chunk.text).where(Chunk.law_id == law.id))).all()
    assert sorted(texts) == ["(א) ראשון", "(א) שני בנוסח חדש"]


async def test_section_that_left_the_law_is_deleted(db_session: AsyncSession, law: Law) -> None:
    embedder = CountingEmbedder()
    both = ParsedLaw(None, [_section("1", "ראשון"), _section("2", "שני")], [])
    only_first = ParsedLaw(None, [_section("1", "ראשון")], [])
    await index_law(db_session, law, both, embedder)

    stats = await index_law(db_session, law, only_first, embedder)

    assert stats.removed == 1
    numbers = (
        await db_session.scalars(select(Chunk.section_number).where(Chunk.law_id == law.id))
    ).all()
    assert list(numbers) == ["1"]


async def test_renaming_the_law_recomputes_the_vectors(db_session: AsyncSession, law: Law) -> None:
    embedder = CountingEmbedder()
    parsed = ParsedLaw(None, [_section("1", "ראשון")], [])
    await index_law(db_session, law, parsed, embedder)
    law.wikisource_title = "שם חדש לחוק"

    stats = await index_law(db_session, law, parsed, embedder)

    assert (stats.added, stats.removed, stats.embedded) == (1, 1, 1)


async def test_a_different_model_recomputes_and_records_its_name(
    db_session: AsyncSession, law: Law
) -> None:
    parsed = ParsedLaw(None, [_section("1", "ראשון")], [])
    await index_law(db_session, law, parsed, CountingEmbedder("model-a"))

    stats = await index_law(db_session, law, parsed, CountingEmbedder("model-b"))

    assert (stats.added, stats.removed, stats.kept, stats.embedded) == (0, 0, 0, 1)
    models = (
        await db_session.scalars(select(Chunk.embedding_model).where(Chunk.law_id == law.id))
    ).all()
    assert list(models) == ["model-b"]
