import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.embeddings.fake import HashEmbedder
from labor_rights_rag.persistence.models import Chunk, Law
from labor_rights_rag.retrieval.bm25 import Bm25Index, bm25_search
from labor_rights_rag.retrieval.hybrid import hybrid_search
from labor_rights_rag.retrieval.normalize import to_search_text


def index(*texts: str, law: int = 1) -> Bm25Index:
    return Bm25Index((i, law, text) for i, text in enumerate(texts, start=1))


def ids(top: list[tuple[int, float]]) -> list[int]:
    return [chunk_id for chunk_id, _ in top]


# The scoring itself


def test_a_chunk_with_the_rare_word_beats_chunks_with_the_common_one() -> None:
    # Every chunk has one match: "שכר" is in three chunks, "14א" in one. Without rarity the
    # scores tie and chunk 1 would come first; with it the chunk of "14א" wins.
    idx = index("שכר", "שכר", "שכר", "14א")

    assert ids(idx.top(["שכר", "14א"], 4))[0] == 4


def test_a_word_in_every_chunk_is_worth_almost_nothing() -> None:
    idx = index("שכר", "שכר", "שכר")

    assert idx.top(["שכר"], 3)[0][1] < 0.3


def test_the_same_match_counts_for_more_in_a_short_chunk_than_in_a_long_one() -> None:
    idx = index("חופשה", "חופשה " + "מילה " * 30, "אחר לגמרי")

    top = idx.top(["חופשה"], 3)

    assert ids(top) == [1, 2]
    assert top[0][1] > top[1][1]


def test_repeating_a_word_adds_less_each_time() -> None:
    once = index("חופשה מילה", "אחר")
    ten = index("חופשה " * 10 + "מילה", "אחר")

    one, many = once.top(["חופשה"], 1)[0][1], ten.top(["חופשה"], 1)[0][1]

    assert one < many < 10 * one


def test_words_the_corpus_does_not_have_find_nothing() -> None:
    idx = index("חופשה שנתית")

    assert idx.top(["הבראה"], 5) == []
    assert idx.top([], 5) == []
    assert Bm25Index([]).top(["חופשה"], 5) == []


def test_equal_scores_come_out_in_the_same_order_every_time() -> None:
    idx = index("חופשה", "חופשה", "חופשה")

    assert ids(idx.top(["חופשה"], 3)) == [1, 2, 3]


def test_a_filter_by_law_returns_only_that_law() -> None:
    idx = Bm25Index([(1, 10, "חופשה"), (2, 20, "חופשה")])

    assert ids(idx.top(["חופשה"], 5, law_odata_id=20)) == [2]


def test_limit_applies() -> None:
    assert len(index("חופשה", "חופשה", "חופשה").top(["חופשה"], 2)) == 2


# Over the database


LAW = 999013
embedder = HashEmbedder()


def _chunk(section: str, text: str) -> Chunk:
    return Chunk(
        section_number=section,
        text=text,
        content_hash=f"h-{section}",
        embedding=embedder.embed_documents([text])[0],
        embedding_model=embedder.name,
        search_text=to_search_text(f"חוק לבדיקה\n{section}. כותרת\n{text}"),
    )


@pytest.fixture
async def seeded(db_session: AsyncSession) -> tuple[AsyncSession, Bm25Index]:
    law = Law(
        odata_id=LAW,
        name="חוק לבדיקה",
        wikisource_title="חוק לבדיקה",
        chunks=[
            _chunk("1", "קלמרפוז טורבינה מגיעה לעובד"),
            _chunk("2", "זמזמוז אחר לגמרי"),
            _chunk("14א", "תחילת התקנה"),
        ],
    )
    db_session.add(law)
    await db_session.flush()
    # Only the seeded chunks: the development database may also hold the real laws.
    return db_session, Bm25Index((c.id, LAW, c.search_text or "") for c in law.chunks)


async def test_bm25_search_returns_hits_with_the_chunk_details(
    seeded: tuple[AsyncSession, Bm25Index],
) -> None:
    session, idx = seeded

    hits = await bm25_search(session, idx, "קלמרפוז", k=5)

    assert [(h.rank, h.section_number, h.law_odata_id) for h in hits] == [(1, "1", LAW)]
    assert hits[0].text == "קלמרפוז טורבינה מגיעה לעובד"
    assert hits[0].score > 0


async def test_bm25_finds_a_section_by_its_number(seeded: tuple[AsyncSession, Bm25Index]) -> None:
    session, idx = seeded

    hits = await bm25_search(session, idx, "סעיף 14א לחוק", k=5)

    assert hits[0].section_number == "14א"


async def test_a_question_without_known_words_finds_nothing(
    seeded: tuple[AsyncSession, Bm25Index],
) -> None:
    session, idx = seeded

    assert await bm25_search(session, idx, "מה כמה לי", k=5) == []
    assert await bm25_search(session, idx, "משהו שאין", k=5) == []


async def test_hybrid_can_use_bm25_for_the_word_side(
    seeded: tuple[AsyncSession, Bm25Index],
) -> None:
    session, idx = seeded

    found = await hybrid_search(
        session, embedder, "קלמרפוז טורבינה", k=3, law_odata_id=LAW, bm25=idx
    )

    assert found.hits[0].section_number == "1"
    assert found.hits[0].text_rank == 1 and found.hits[0].vector_rank == 1
