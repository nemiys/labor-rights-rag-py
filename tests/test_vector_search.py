from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.api.dependencies import get_embedder
from labor_rights_rag.embeddings.fake import HashEmbedder
from labor_rights_rag.main import create_app
from labor_rights_rag.persistence.database import get_session
from labor_rights_rag.persistence.models import Chunk, Law
from labor_rights_rag.retrieval.vector import use_exact_vector_scan, vector_search
from labor_rights_rag.settings import settings

LEAVE = "עובד זכאי לחופשה שנתית בת ימים"
OVERTIME = "שעות נוספות משולמות בתוספת"
# Ids that no real law has: the development database may already hold the real ones.
LAW_A, LAW_B = 999004, 999005

embedder = HashEmbedder()


def _chunk(section: str, text: str, model: str | None = None, embedded: bool = True) -> Chunk:
    return Chunk(
        section_number=section,
        text=text,
        content_hash=f"h-{section}-{text}",
        embedding=embedder.embed_documents([text])[0] if embedded else None,
        embedding_model=(model or embedder.name) if embedded else None,
    )


def _law(odata_id: int, chunks: list[Chunk]) -> Law:
    return Law(odata_id=odata_id, name=f"חוק {odata_id}", wikisource_title="חוק", chunks=chunks)


@pytest.fixture
async def seeded(db_session: AsyncSession) -> AsyncSession:
    db_session.add(_law(LAW_A, [_chunk("1", LEAVE), _chunk("2", OVERTIME)]))
    await db_session.flush()
    return db_session


async def test_closest_chunk_comes_first_with_rank_and_score(seeded: AsyncSession) -> None:
    hits = await vector_search(seeded, embedder, "כמה ימי חופשה שנתית", k=5, law_odata_id=LAW_A)

    assert [(h.rank, h.section_number) for h in hits] == [(1, "1"), (2, "2")]
    assert hits[0].score > hits[1].score


async def test_order_follows_closeness_not_the_order_of_insertion(seeded: AsyncSession) -> None:
    # Section "2" was stored second but is the one this question is about.
    hits = await vector_search(seeded, embedder, "שעות נוספות", k=5, law_odata_id=LAW_A)

    assert [h.section_number for h in hits] == ["2", "1"]


async def test_identical_text_has_similarity_one(seeded: AsyncSession) -> None:
    hits = await vector_search(seeded, embedder, LEAVE, k=1, law_odata_id=LAW_A)

    assert abs(hits[0].score - 1.0) < 1e-6


async def test_k_limits_the_number_of_hits(seeded: AsyncSession) -> None:
    hits = await vector_search(seeded, embedder, LEAVE, k=1, law_odata_id=LAW_A)

    assert len(hits) == 1


async def test_law_filter_returns_only_that_law(db_session: AsyncSession) -> None:
    db_session.add_all([_law(LAW_A, [_chunk("1", LEAVE)]), _law(LAW_B, [_chunk("9", LEAVE)])])
    await db_session.flush()

    hits = await vector_search(db_session, embedder, LEAVE, k=5, law_odata_id=LAW_B)

    assert [(h.law_odata_id, h.section_number) for h in hits] == [(LAW_B, "9")]


async def test_chunk_of_another_model_is_not_returned(db_session: AsyncSession) -> None:
    db_session.add(_law(LAW_A, [_chunk("1", LEAVE, model="other-model")]))
    await db_session.flush()

    assert await vector_search(db_session, embedder, LEAVE, k=5, law_odata_id=LAW_A) == []


async def test_chunk_without_a_vector_is_not_returned(db_session: AsyncSession) -> None:
    db_session.add(_law(LAW_A, [_chunk("1", LEAVE, embedded=False)]))
    await db_session.flush()

    assert await vector_search(db_session, embedder, LEAVE, k=5, law_odata_id=LAW_A) == []


@pytest.fixture
async def client(seeded: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def session() -> AsyncIterator[AsyncSession]:
        yield seeded

    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_embedder] = lambda: embedder
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


async def test_search_endpoint_returns_hits_in_the_documented_shape(client: AsyncClient) -> None:
    response = await client.get(
        "/search", params={"q": " ימי חופשה שנתית ", "law": LAW_A, "mode": "vector"}
    )

    body = response.json()
    assert response.status_code == 200
    assert (body["query"], body["mode"], body["k"]) == ("ימי חופשה שנתית", "vector", 5)
    first = body["hits"][0]
    assert set(first) == {
        "rank",
        "score",
        "law",
        "law_id",
        "section",
        "part",
        "text",
        "vector_rank",
        "text_rank",
    }
    assert (first["rank"], first["law_id"], first["section"], first["part"]) == (1, LAW_A, "1", 0)
    assert first["text"] == LEAVE


@pytest.mark.parametrize(
    "params",
    [
        {},  # no question
        {"q": "   "},  # a blank question
        {"q": "חופשה", "k": 0},
        {"q": "חופשה", "k": 51},
        {"q": "חופשה", "mode": "semantic"},  # not a mode
        {"q": "חופשה", "law": "not-a-number"},
    ],
)
async def test_search_endpoint_rejects_bad_parameters(
    client: AsyncClient, params: dict[str, str | int]
) -> None:
    response = await client.get("/search", params=params)

    assert response.status_code == 422


async def test_vector_queries_are_exact_by_default(seeded: AsyncSession) -> None:
    await use_exact_vector_scan(seeded)

    # With the index scan switched off the planner takes the exact table scan.
    assert (await seeded.execute(text("SHOW enable_indexscan"))).scalar() == "off"


async def test_with_the_index_on_the_scan_goes_on_until_it_has_enough_rows(
    seeded: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "vector_index", True)

    await use_exact_vector_scan(seeded)

    assert (await seeded.execute(text("SHOW hnsw.iterative_scan"))).scalar() == "strict_order"
    assert (await seeded.execute(text("SHOW enable_indexscan"))).scalar() == "on"
