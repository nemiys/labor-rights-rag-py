"""Integration tests for the tables and their rules, against a real Postgres."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.persistence.models import Chunk, Law


def _law(odata_id: int = 999001) -> Law:
    return Law(odata_id=odata_id, name="חוק לדוגמה", wikisource_title="חוק לדוגמה")


async def test_vector_extension_is_enabled(db_session: AsyncSession) -> None:
    result = await db_session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))

    assert result.scalar() == 1


async def test_law_defaults_to_unknown_currency(db_session: AsyncSession) -> None:
    law = _law()
    db_session.add(law)
    await db_session.flush()

    assert law.currency_status == "unknown"


async def test_invalid_currency_status_is_rejected(db_session: AsyncSession) -> None:
    law = _law()
    law.currency_status = "stale"
    db_session.add(law)

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_same_chunk_text_is_not_stored_twice(db_session: AsyncSession) -> None:
    law = _law()
    law.chunks = [
        Chunk(section_number="3", text="טקסט", content_hash="h1"),
        Chunk(section_number="3", text="טקסט", content_hash="h1"),
    ]
    db_session.add(law)

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_deleting_a_law_deletes_its_chunks(db_session: AsyncSession) -> None:
    law = _law()
    law.chunks = [Chunk(section_number="1", text="טקסט", content_hash="h1")]
    db_session.add(law)
    await db_session.flush()

    await db_session.delete(law)
    await db_session.flush()

    remaining = await db_session.execute(select(Chunk).where(Chunk.section_number == "1"))
    assert remaining.scalars().all() == []
