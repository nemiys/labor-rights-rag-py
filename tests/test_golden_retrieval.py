"""A short golden test of the whole retrieval chain, offline: no network, no model, no key.

Two real laws (saved pages) go through the real parsing, chunking and indexing, with the
fake embedder; then a few plain questions must find the section that answers them.

This tests the plumbing, not the quality of search. The fake embedder knows no meaning, so
what is checked about vector search is that it is wired; what is checked about text search
is real (Hebrew normalization on real law text). The evaluation questions, which measure
quality, are a separate set that is written by hand in stage 6.
"""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.embeddings.fake import HashEmbedder
from labor_rights_rag.ingest.indexing import index_law
from labor_rights_rag.parsing.wikitext import parse_law
from labor_rights_rag.persistence.models import Law
from labor_rights_rag.retrieval.hybrid import hybrid_search
from labor_rights_rag.retrieval.text import text_search

FIXTURES = Path(__file__).parent / "fixtures" / "wikisource"
# Ids that no real law has: the development database may already hold the real ones.
LEAVE, NOTICE = 999009, 999010
embedder = HashEmbedder()


@pytest.fixture
async def indexed(db_session: AsyncSession) -> AsyncSession:
    for odata_id, title, page in (
        (LEAVE, "חוק חופשה שנתית", "annual_leave"),
        (NOTICE, "חוק הודעה מוקדמת לפיטורים ולהתפטרות", "advance_notice"),
    ):
        law = Law(odata_id=odata_id, name=title, wikisource_title=title)
        db_session.add(law)
        await db_session.flush()
        parsed = parse_law((FIXTURES / f"{page}.wiki").read_text(encoding="utf-8"))
        await index_law(db_session, law, parsed, embedder)
    return db_session


# (law, a plain question, the section that answers it). Each answer was checked in the saved
# page: 11 says when vacation pay is paid, 13 buys back unused vacation when the work ends,
# 31 sets the limitation period, 7 is what happens without notice, 9 gives the labor court
# its jurisdiction, 28 is the offences section.
LEXICAL = [
    (LEAVE, "כמה זמן יש להגיש תביעה, ההתישנות", "31"),
    (LEAVE, "סעיף 28", "28"),
    (NOTICE, "מה קורה אם המעסיק פיטר ולא נתן הודעה מוקדמת", "7"),
    (NOTICE, "איזה בית דין מוסמך לדון בתביעה", "9"),
]
# The question and the section use different forms of the word: "משולמים" and "ישולמו",
# "הפסיק" and "חדל". The words they share ("דמי", "חופשה", "עובד") are in every section of the
# law, so word search cannot tell the section apart (ADR-0006). Only the hybrid search is
# expected to find these; here the fake embedder does it by counting words, not by meaning.
WORDS_DIFFER = [
    (LEAVE, "מתי משולמים דמי החופשה", "11"),
    (LEAVE, "עובד הפסיק לעבוד ולא קיבל את החופשה, מה מגיע לו", "13"),
]
GOLDEN = LEXICAL + WORDS_DIFFER


@pytest.mark.parametrize(("law", "question", "expected"), LEXICAL)
async def test_text_search_finds_the_answering_section(
    indexed: AsyncSession, law: int, question: str, expected: str
) -> None:
    hits = await text_search(indexed, question, k=3, law_odata_id=law)

    assert expected in [h.section_number for h in hits]


@pytest.mark.parametrize(("law", "question", "expected"), GOLDEN)
async def test_hybrid_search_finds_the_answering_section(
    indexed: AsyncSession, law: int, question: str, expected: str
) -> None:
    hits = (await hybrid_search(indexed, embedder, question, k=3, law_odata_id=law)).hits

    assert expected in [h.section_number for h in hits]
