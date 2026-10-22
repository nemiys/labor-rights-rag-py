"""Integration tests against a real Postgres with pgvector (docker compose up -d postgres).

Skipped when the database is not reachable, so a plain `pytest` still works offline.
"""

import socket
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from labor_rights_rag.persistence.models import Chunk, Law
from labor_rights_rag.settings import settings


def _database_reachable() -> bool:
    parsed = urlparse(settings.database_url.replace("+asyncpg", ""))
    try:
        with socket.create_connection((parsed.hostname or "localhost", parsed.port or 5432), 1):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not _database_reachable(), reason="Postgres is not reachable")


@pytest.fixture(scope="module", autouse=True)
def migrated_database() -> None:
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(settings.database_url)
    async with AsyncSession(engine) as session:
        yield session
        await session.rollback()  # every test leaves the database untouched
    await engine.dispose()


def _law(odata_id: int = 999001) -> Law:
    return Law(odata_id=odata_id, name="חוק לדוגמה", wikisource_title="חוק לדוגמה")


async def test_vector_extension_is_enabled(session: AsyncSession) -> None:
    result = await session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))

    assert result.scalar() == 1


async def test_law_defaults_to_unknown_currency(session: AsyncSession) -> None:
    law = _law()
    session.add(law)
    await session.flush()

    assert law.currency_status == "unknown"


async def test_invalid_currency_status_is_rejected(session: AsyncSession) -> None:
    law = _law()
    law.currency_status = "stale"
    session.add(law)

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_same_chunk_text_is_not_stored_twice(session: AsyncSession) -> None:
    law = _law()
    law.chunks = [
        Chunk(section_number="3", text="טקסט", content_hash="h1"),
        Chunk(section_number="3", text="טקסט", content_hash="h1"),
    ]
    session.add(law)

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_deleting_a_law_deletes_its_chunks(session: AsyncSession) -> None:
    law = _law()
    law.chunks = [Chunk(section_number="1", text="טקסט", content_hash="h1")]
    session.add(law)
    await session.flush()

    await session.delete(law)
    await session.flush()

    remaining = await session.execute(select(Chunk).where(Chunk.section_number == "1"))
    assert remaining.scalars().all() == []
