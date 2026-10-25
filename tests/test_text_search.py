from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.api.dependencies import get_embedder
from labor_rights_rag.embeddings.fake import HashEmbedder
from labor_rights_rag.main import create_app
from labor_rights_rag.persistence.database import get_session
from labor_rights_rag.persistence.models import Chunk, Law
from labor_rights_rag.retrieval.normalize import to_search_text
from labor_rights_rag.retrieval.text import text_search

# Ids that no real law has: the development database may already hold the real ones.
LAW_A, LAW_B = 999006, 999007


def _chunk(section: str, text: str) -> Chunk:
    return Chunk(
        section_number=section,
        text=text,
        content_hash=f"h-{section}-{text}",
        # As the indexing step builds it: a header with the section number, then the body.
        search_text=to_search_text(f"חוק לדוגמה\n{section}. כותרת\n{text}"),
    )


def _law(odata_id: int, chunks: list[Chunk]) -> Law:
    return Law(odata_id=odata_id, name=f"חוק {odata_id}", wikisource_title="חוק", chunks=chunks)


@pytest.fixture
async def seeded(db_session: AsyncSession) -> AsyncSession:
    db_session.add(
        _law(
            LAW_A,
            [
                _chunk("1", "עובד זכאי לחופשה שנתית בת ארבעה עשר ימים"),
                _chunk("2", "שעות נוספות משולמות בתוספת של עשרים וחמישה אחוזים"),
                _chunk("14א", "תחילתו של חוק זה ביום פרסומו"),
                _chunk("3", "חופשה שנתית ושעות נוספות בשבוע העבודה"),
            ],
        )
    )
    await db_session.flush()
    return db_session


async def _sections(session: AsyncSession, query: str, **kwargs: int) -> list[str]:
    hits = await text_search(session, query, k=kwargs.pop("k", 5), law_odata_id=LAW_A, **kwargs)
    return [hit.section_number for hit in hits]


async def test_a_word_finds_the_same_word_with_a_prefix(seeded: AsyncSession) -> None:
    # The text says "לחופשה"; the question says "חופשה".
    assert "1" in await _sections(seeded, "חופשה")


async def test_a_word_with_a_prefix_finds_the_bare_word(seeded: AsyncSession) -> None:
    # The question says "בשעות"; the text says "שעות".
    assert "2" in await _sections(seeded, "בשעות")


async def test_a_section_number_is_found_exactly(seeded: AsyncSession) -> None:
    assert await _sections(seeded, "סעיף 14א") == ["14א"]


async def test_chunk_with_more_of_the_words_ranks_higher(seeded: AsyncSession) -> None:
    hits = await text_search(seeded, "חופשה שנתית שעות נוספות", k=5, law_odata_id=LAW_A)

    assert hits[0].section_number == "3"
    assert [h.rank for h in hits] == list(range(1, len(hits) + 1))
    assert hits[0].score >= hits[-1].score


async def test_question_words_alone_find_nothing(seeded: AsyncSession) -> None:
    assert await _sections(seeded, "מה כמה לי") == []


async def test_a_word_that_is_nowhere_finds_nothing(seeded: AsyncSession) -> None:
    assert await _sections(seeded, "הבראה") == []


async def test_special_characters_in_the_question_are_harmless(seeded: AsyncSession) -> None:
    assert await _sections(seeded, "'); DROP TABLE chunks; -- | & ! ( ) :*") == []


async def test_k_limits_the_number_of_hits(seeded: AsyncSession) -> None:
    assert len(await _sections(seeded, "חופשה שעות", k=1)) == 1


async def test_law_filter_returns_only_that_law(db_session: AsyncSession) -> None:
    db_session.add_all(
        [_law(LAW_A, [_chunk("1", "חופשה שנתית")]), _law(LAW_B, [_chunk("9", "חופשה שנתית")])]
    )
    await db_session.flush()

    hits = await text_search(db_session, "חופשה", k=5, law_odata_id=LAW_B)

    assert [(h.law_odata_id, h.section_number) for h in hits] == [(LAW_B, "9")]


async def test_chunk_not_yet_normalized_is_never_found(db_session: AsyncSession) -> None:
    db_session.add(_law(LAW_A, [Chunk(section_number="1", text="חופשה", content_hash="h")]))
    await db_session.flush()

    assert await text_search(db_session, "חופשה", k=5, law_odata_id=LAW_A) == []


@pytest.fixture
async def client(seeded: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def session() -> AsyncIterator[AsyncSession]:
        yield seeded

    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


async def test_search_endpoint_in_text_mode(client: AsyncClient) -> None:
    response = await client.get("/search", params={"q": "סעיף 14א", "mode": "text", "law": LAW_A})

    body = response.json()
    assert response.status_code == 200
    assert body["mode"] == "text"
    assert [(h["rank"], h["section"]) for h in body["hits"]] == [(1, "14א")]
