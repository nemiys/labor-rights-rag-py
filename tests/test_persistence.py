"""Integration tests for the tables and their rules, against a real Postgres."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.embeddings.fake import HashEmbedder
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


async def test_nearest_chunk_by_cosine_distance_is_the_one_sharing_the_words(
    db_session: AsyncSession,
) -> None:
    embedder = HashEmbedder()
    texts = {"1": "עובד זכאי לחופשה שנתית בת ימים", "2": "שעות נוספות משולמות בתוספת"}
    law = _law()
    law.chunks = [
        Chunk(
            section_number=number,
            text=body,
            content_hash=f"h{number}",
            embedding=embedder.embed_documents([body])[0],
            embedding_model=embedder.name,
        )
        for number, body in texts.items()
    ]
    db_session.add(law)
    await db_session.flush()

    question = embedder.embed_query("כמה ימי חופשה שנתית")
    nearest = await db_session.execute(
        select(Chunk.section_number, Chunk.embedding_model)
        .where(Chunk.law_id == law.id)
        .order_by(Chunk.embedding.cosine_distance(question))
        .limit(1)
    )

    assert nearest.one() == ("1", "hash-fake")


async def test_chunk_can_be_stored_before_it_is_embedded(db_session: AsyncSession) -> None:
    law = _law()
    law.chunks = [Chunk(section_number="1", text="טקסט", content_hash="h1")]
    db_session.add(law)
    await db_session.flush()

    assert law.chunks[0].embedding is None
    assert law.chunks[0].embedding_model is None
