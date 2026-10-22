"""Shared fixtures. Database tests need Postgres with pgvector (docker compose up -d postgres)
and are skipped when it is not reachable, so a plain `pytest` still works offline."""

import socket
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from labor_rights_rag.settings import settings


def _database_reachable() -> bool:
    parsed = urlparse(settings.database_url.replace("+asyncpg", ""))
    try:
        with socket.create_connection((parsed.hostname or "localhost", parsed.port or 5432), 1):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def migrated_database() -> None:
    if not _database_reachable():
        pytest.skip("Postgres is not reachable")
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
async def db_session(migrated_database: None) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(settings.database_url)
    async with AsyncSession(engine) as session:
        yield session
        await session.rollback()  # every test leaves the database untouched
    await engine.dispose()
