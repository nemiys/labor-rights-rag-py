from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.api.dependencies import get_embedder
from labor_rights_rag.embeddings.fake import HashEmbedder
from labor_rights_rag.main import create_app
from labor_rights_rag.persistence.database import get_session
from labor_rights_rag.persistence.models import Chunk, Law
from labor_rights_rag.retrieval.hit import Hit
from labor_rights_rag.retrieval.hybrid import hybrid_search, reciprocal_rank_fusion
from labor_rights_rag.retrieval.normalize import to_search_text


def hit(chunk_id: int, rank: int) -> Hit:
    return Hit(rank, 0.5, chunk_id, 1, "חוק", str(chunk_id), 0, f"טקסט {chunk_id}")


def ids(hits: list[Hit]) -> list[int]:
    return [h.chunk_id for h in hits]


def test_a_chunk_found_by_both_searches_beats_one_found_by_a_single_search() -> None:
    # The example from ADR-0007: A is 1st by meaning and 2nd by words, B only 1st by words.
    fused = reciprocal_rank_fusion([hit(1, 1)], [hit(2, 1), hit(1, 2)], k=60)

    assert ids(fused) == [1, 2]
    assert fused[0].score == pytest.approx(1 / 61 + 1 / 62)
    assert fused[1].score == pytest.approx(1 / 61)


def test_one_list_keeps_its_order() -> None:
    fused = reciprocal_rank_fusion([hit(3, 1), hit(1, 2), hit(2, 3)], [])

    assert ids(fused) == [3, 1, 2]


def test_ranks_start_at_one_and_the_rank_in_each_search_is_kept() -> None:
    fused = reciprocal_rank_fusion([hit(1, 1), hit(2, 2)], [hit(2, 1)])

    assert [h.rank for h in fused] == [1, 2]
    by_id = {h.chunk_id: h for h in fused}
    assert (by_id[1].vector_rank, by_id[1].text_rank) == (1, None)
    assert (by_id[2].vector_rank, by_id[2].text_rank) == (2, 1)


def test_k_decides_how_much_a_top_rank_is_worth() -> None:
    # Chunk 10 is 4th in both searches. Chunks 21 and 31 are each 1st in one search only.
    vector = [hit(21, 1), hit(22, 2), hit(23, 3), hit(10, 4)]
    text = [hit(31, 1), hit(32, 2), hit(33, 3), hit(10, 4)]

    assert reciprocal_rank_fusion(vector, text, k=60)[0].chunk_id == 10  # found twice wins
    assert reciprocal_rank_fusion(vector, text, k=1)[0].chunk_id == 21  # a first place wins


def test_equal_scores_are_ordered_the_same_way_every_time() -> None:
    # Chunk 5 is 1st by meaning, chunk 3 is 1st by words: equal scores, equal best rank.
    first = reciprocal_rank_fusion([hit(5, 1)], [hit(3, 1)])
    second = reciprocal_rank_fusion([hit(5, 1)], [hit(3, 1)])

    assert ids(first) == ids(second) == [3, 5]  # the lower id first


def test_nothing_found_gives_nothing() -> None:
    assert reciprocal_rank_fusion([], []) == []


# Ids that no real law has: the development database may already hold the real ones.
LAW = 999008
embedder = HashEmbedder()


def _chunk(section: str, text: str, vector: bool = True, words: bool = True) -> Chunk:
    return Chunk(
        section_number=section,
        text=text,
        content_hash=f"h-{section}",
        embedding=embedder.embed_documents([text])[0] if vector else None,
        embedding_model=embedder.name if vector else None,
        search_text=to_search_text(f"חוק לדוגמה\n{section}. כותרת\n{text}") if words else None,
    )


@pytest.fixture
async def seeded(db_session: AsyncSession) -> AsyncSession:
    db_session.add(
        Law(
            odata_id=LAW,
            name="חוק לדוגמה",
            wikisource_title="חוק לדוגמה",
            chunks=[
                _chunk("1", "עובד זכאי לחופשה שנתית"),
                _chunk("2", "חופשה שנתית בלי וקטור", vector=False),  # only words can find it
                _chunk("3", "חופשה שנתית בלי מילים", words=False),  # only meaning can find it
            ],
        )
    )
    await db_session.flush()
    return db_session


async def test_hybrid_returns_what_either_search_found(seeded: AsyncSession) -> None:
    hits = await hybrid_search(seeded, embedder, "חופשה שנתית", k=5, law_odata_id=LAW)

    by_section = {h.section_number: h for h in hits}
    assert set(by_section) == {"1", "2", "3"}
    assert by_section["1"].rank == 1  # found by both
    assert by_section["2"].vector_rank is None and by_section["2"].text_rank is not None
    assert by_section["3"].text_rank is None and by_section["3"].vector_rank is not None


async def test_hybrid_returns_at_most_k(seeded: AsyncSession) -> None:
    hits = await hybrid_search(seeded, embedder, "חופשה שנתית", k=2, law_odata_id=LAW)

    assert [h.rank for h in hits] == [1, 2]


async def test_hybrid_works_when_the_question_is_only_question_words(seeded: AsyncSession) -> None:
    # Text search has nothing to look for; the meaning search still answers.
    hits = await hybrid_search(seeded, embedder, "מה כמה לי", k=5, law_odata_id=LAW)

    assert all(h.text_rank is None for h in hits)


@pytest.fixture
async def client(seeded: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def session() -> AsyncIterator[AsyncSession]:
        yield seeded

    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_embedder] = lambda: embedder
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


async def test_search_endpoint_is_hybrid_by_default_and_shows_both_ranks(
    client: AsyncClient,
) -> None:
    response = await client.get("/search", params={"q": "חופשה שנתית", "law": LAW})

    body = response.json()
    assert response.status_code == 200
    assert body["mode"] == "hybrid"
    first = body["hits"][0]
    assert first["section"] == "1"  # the only chunk that both searches found
    assert first["text_rank"] == 1
    assert first["vector_rank"] is not None
