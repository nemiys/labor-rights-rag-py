from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.evaluation.baselines import (
    CLOSED_BOOK_SYSTEM_PROMPT,
    ClosedBookAnswerer,
    ask_closed_book,
    load_all_hits,
)
from labor_rights_rag.generation.ask import answer_from_hits
from labor_rights_rag.generation.base import ModelResponse
from labor_rights_rag.generation.messages import REFUSAL_MESSAGE
from labor_rights_rag.generation.prompt import NO_ANSWER_MARKER
from labor_rights_rag.persistence.models import Chunk, Law
from labor_rights_rag.retrieval.hit import Hit

# Ids that no real law has: the development database may already hold the real ones.
LAW_ID = 999021


class Scripted:
    name = "scripted"

    def __init__(self, text: str) -> None:
        self.text = text
        self.seen: Sequence[Hit] | None = None

    async def answer(self, question: str, hits: Sequence[Hit]) -> ModelResponse:
        self.seen = hits
        return ModelResponse(self.text, self.name, 10, 5, 0.5)


def test_the_closed_book_prompt_has_no_sources_and_lets_the_model_say_it_does_not_know() -> None:
    answerer = ClosedBookAnswerer("http://localhost", None, "m")

    prompt = answerer._prompt("כמה ימי חופש?", [])

    assert prompt.system == CLOSED_BOOK_SYSTEM_PROMPT
    assert "<source" not in prompt.user
    assert "כמה ימי חופש?" in prompt.user
    assert NO_ANSWER_MARKER in prompt.system
    assert "using only the numbered sources" not in prompt.system  # not the rules of the system


async def test_a_closed_book_answer_is_taken_as_written_with_nothing_to_cite() -> None:
    answerer = Scripted("מגיעים 14 ימים.")

    result = await ask_closed_book(answerer, "שאלה")

    assert (result.status, result.answer, result.citations) == ("answered", "מגיעים 14 ימים.", [])
    assert answerer.seen == []  # no sources were given
    assert (result.model, result.input_tokens, result.output_tokens) == ("scripted", 10, 5)


@pytest.mark.parametrize("text", [NO_ANSWER_MARKER, f"  {NO_ANSWER_MARKER}", "   ", ""])
async def test_a_closed_book_model_that_does_not_know_is_a_refusal(text: str) -> None:
    result = await ask_closed_book(Scripted(text), "שאלה")

    assert (result.status, result.answer) == ("refused_by_model", REFUSAL_MESSAGE)


async def test_the_marker_after_a_partial_closed_book_answer_is_not_shown() -> None:
    result = await ask_closed_book(Scripted(f"חלק מהתשובה. {NO_ANSWER_MARKER}"), "שאלה")

    assert result.status == "answered"
    assert NO_ANSWER_MARKER not in result.answer


@pytest.fixture
async def seeded(db_session: AsyncSession) -> AsyncSession:
    chunks = [
        Chunk(section_number=str(n), text=f"טקסט {n}", content_hash=f"b-{n}", chunk_index=0)
        for n in (1, 2, 3)
    ]
    db_session.add(
        Law(
            odata_id=LAW_ID,
            name="חוק לבדיקה",
            wikisource_title="חוק לבדיקה",
            currency_status="ok",
            fetched_at=datetime(2026, 10, 22, tzinfo=UTC),
            chunks=chunks,
        )
    )
    # Added after the first law but with a smaller id: it must still come first.
    db_session.add(
        Law(
            odata_id=LAW_ID - 1,
            name="חוק קודם",
            wikisource_title="חוק קודם",
            currency_status="ok",
            fetched_at=datetime(2026, 10, 22, tzinfo=UTC),
            chunks=[Chunk(section_number="9", text="טקסט 9", content_hash="b-9", chunk_index=0)],
        )
    )
    await db_session.flush()
    return db_session


async def test_all_the_laws_are_every_chunk_numbered_in_order(seeded: AsyncSession) -> None:
    hits = await load_all_hits(seeded)

    ours = [h for h in hits if h.law_odata_id == LAW_ID]
    assert [h.section_number for h in ours] == ["1", "2", "3"]
    both = [
        (h.law_odata_id, h.section_number) for h in hits if h.law_odata_id in (LAW_ID - 1, LAW_ID)
    ]
    assert both == [(LAW_ID - 1, "9"), (LAW_ID, "1"), (LAW_ID, "2"), (LAW_ID, "3")]
    assert [h.rank for h in hits] == list(range(1, len(hits) + 1))  # 1..n with no gaps
    assert ours[0].law_name == "חוק לבדיקה"
    assert ours[0].text == "טקסט 1"


async def test_with_all_the_laws_a_citation_is_checked_like_in_the_system(
    seeded: AsyncSession,
) -> None:
    hits = [h for h in await load_all_hits(seeded) if h.law_odata_id == LAW_ID]

    good = await answer_from_hits(seeded, Scripted("טענה [2]."), "שאלה", hits)
    made_up = await answer_from_hits(seeded, Scripted("טענה [9]."), "שאלה", hits)
    uncited = await answer_from_hits(seeded, Scripted("טענה בלי מקור."), "שאלה", hits)

    assert good.status == "answered" and good.citations[0].card.section == "2"
    assert made_up.status == "rejected_invalid_citations"
    assert uncited.status == "rejected_no_citations"
