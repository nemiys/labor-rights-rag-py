from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.api.dependencies import get_answerer, get_embedder
from labor_rights_rag.embeddings.fake import HashEmbedder
from labor_rights_rag.generation.ask import AskResult, ask
from labor_rights_rag.generation.base import ModelResponse
from labor_rights_rag.generation.card import build_card
from labor_rights_rag.generation.fake import FakeAnswerer
from labor_rights_rag.generation.messages import CURRENCY_WARNINGS, DISCLAIMER, REFUSAL_MESSAGE
from labor_rights_rag.generation.prompt import NO_ANSWER_MARKER
from labor_rights_rag.main import create_app
from labor_rights_rag.persistence.database import get_session
from labor_rights_rag.persistence.models import Chunk, Law
from labor_rights_rag.retrieval.hit import Hit
from labor_rights_rag.retrieval.normalize import to_search_text
from labor_rights_rag.settings import settings

# Ids that no real law has: the development database may already hold the real ones.
LAW_ID = 999011
QUOTE = "עובד זכאי לחופשה שנתית בת ארבעה עשר ימים"
QUESTION = "חופשה שנתית"
embedder = HashEmbedder()


class ScriptedAnswerer:
    """A model that says whatever it is told to, and counts how often it was asked."""

    name = "scripted"

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    async def answer(self, question: str, hits: Sequence[Hit]) -> ModelResponse:
        self.calls += 1
        return ModelResponse(self.text, self.name, input_tokens=10, output_tokens=5, seconds=0.5)


def _chunk(section: str, text: str) -> Chunk:
    return Chunk(
        section_number=section,
        text=text,
        content_hash=f"h-{section}",
        embedding=embedder.embed_documents([text])[0],
        embedding_model=embedder.name,
        search_text=to_search_text(f"חוק לדוגמה\n{section}. כותרת\n{text}"),
    )


def _law(status: str = "ok") -> Law:
    return Law(
        odata_id=LAW_ID,
        name='חוק לדוגמה, התשי"א-1951',
        wikisource_title="חוק לדוגמה",
        currency_status=status,
        fetched_at=datetime(2026, 10, 22, 12, 0, tzinfo=UTC),
        last_amendment_label="תיקון מספר 7",
        last_amendment_url="https://example.org/amendment.pdf",
        chunks=[_chunk("3", QUOTE), _chunk("7", "אין החופשה ניתנת לצבירה")],
    )


@pytest.fixture
async def seeded(db_session: AsyncSession) -> AsyncSession:
    db_session.add(_law())
    await db_session.flush()
    return db_session


async def run(
    session: AsyncSession, answerer: ScriptedAnswerer | FakeAnswerer, min_score: float = 0.0
) -> AskResult:
    # Only the seeded law: the development database may also hold the real laws.
    return await ask(
        session,
        embedder,
        answerer,
        QUESTION,
        k=5,
        min_vector_score=min_score,
        law_odata_id=LAW_ID,
    )


async def test_a_good_answer_comes_with_a_card_for_each_source_it_cites(
    seeded: AsyncSession,
) -> None:
    answerer = ScriptedAnswerer("מגיעים ארבעה עשר ימים [1]. אי אפשר לצבור [2][1].")

    result = await run(seeded, answerer)

    assert result.status == "answered"
    assert result.answer == "מגיעים ארבעה עשר ימים [1]. אי אפשר לצבור [2][1]."
    assert [c.number for c in result.citations] == [1, 2]
    assert result.model == "scripted"
    assert (result.input_tokens, result.output_tokens, result.seconds) == (10, 5, 0.5)


async def test_the_quote_in_the_card_is_the_stored_text_not_the_models_words(
    seeded: AsyncSession,
) -> None:
    result = await run(seeded, ScriptedAnswerer("המודל כתב משהו אחר לגמרי [1]."))

    assert result.citations[0].card.quote in {QUOTE, "אין החופשה ניתנת לצבירה"}
    assert "אחר לגמרי" not in result.citations[0].card.quote


async def test_a_source_cited_twice_gets_one_card(seeded: AsyncSession) -> None:
    result = await run(seeded, ScriptedAnswerer("טענה [1]. עוד טענה [1]."))

    assert [c.number for c in result.citations] == [1]


async def test_when_nothing_is_close_enough_the_model_is_not_called(
    seeded: AsyncSession,
) -> None:
    answerer = ScriptedAnswerer("טענה [1].")

    result = await run(seeded, answerer, min_score=0.99)

    assert result.status == "refused_low_score"
    assert result.answer == REFUSAL_MESSAGE
    assert result.model is None
    assert answerer.calls == 0


@pytest.mark.parametrize(
    ("reply", "status"),
    [
        (NO_ANSWER_MARKER, "refused_by_model"),
        ("טענה שמצטטת [1] ומקור שלא קיים [9].", "rejected_invalid_citations"),
        ("טענה בלי שום מקור.", "rejected_no_citations"),
    ],
)
async def test_a_reply_that_cannot_be_trusted_becomes_the_refusal_sentence(
    seeded: AsyncSession, reply: str, status: str
) -> None:
    result = await run(seeded, ScriptedAnswerer(reply))

    assert result.status == status
    assert result.answer == REFUSAL_MESSAGE
    assert result.citations == []
    assert result.model == "scripted"  # the model was called, and its cost is recorded
    assert result.output_tokens == 5


async def test_the_fake_model_goes_through_the_whole_flow(seeded: AsyncSession) -> None:
    result = await run(seeded, FakeAnswerer())

    assert result.status == "answered"
    assert len(result.citations) == 1


# The card


def _hit() -> Hit:
    return Hit(1, 0.7, 5, LAW_ID, "חוק", "14א", 1, QUOTE)


def test_card_has_the_links_the_dates_and_the_disclaimer() -> None:
    card = build_card(_hit(), _law())

    assert card.law == 'חוק לדוגמה, התשי"א-1951'
    assert (card.section, card.part, card.quote) == ("14א", 1, QUOTE)
    assert str(card.text_as_of) == "2026-10-22"
    assert card.knesset_url == (
        "https://main.knesset.gov.il/Activity/Legislation/Laws/Pages/LawPrimary.aspx"
        f"?t=lawlaws&st=lawlaws&lawitemid={LAW_ID}"
    )
    assert (
        card.wikisource_url
        == "https://he.wikisource.org/wiki/%D7%97%D7%95%D7%A7_%D7%9C%D7%93%D7%95%D7%92%D7%9E%D7%94"
    )
    assert card.last_amendment_url == "https://example.org/amendment.pdf"
    assert "14א" in card.search_hint
    assert card.disclaimer == DISCLAIMER


def test_a_current_law_has_no_warning() -> None:
    assert build_card(_hit(), _law("ok")).currency_warning is None


@pytest.mark.parametrize("status", ["ahead", "behind", "unknown"])
def test_a_law_that_may_not_be_current_has_a_warning(status: str) -> None:
    card = build_card(_hit(), _law(status))

    assert card.currency_warning == CURRENCY_WARNINGS[status]


# The endpoint


@pytest.fixture
async def client(
    seeded: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    monkeypatch.setattr(settings, "min_vector_score", 0.0)
    app = create_app()

    async def session() -> AsyncIterator[AsyncSession]:
        yield seeded

    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_answerer] = lambda: FakeAnswerer()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


async def test_ask_endpoint_returns_the_answer_the_cards_and_the_usage(
    client: AsyncClient,
) -> None:
    response = await client.post("/ask", json={"question": QUESTION})

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "answered"
    assert body["disclaimer"] == DISCLAIMER
    assert set(body["citations"][0]["card"]) >= {"law", "section", "quote", "knesset_url"}
    assert {"model", "input_tokens", "output_tokens", "seconds"} <= set(body)


@pytest.mark.parametrize(
    "body", [{}, {"question": ""}, {"question": "   "}, {"question": "ש" * 1001}]
)
async def test_ask_endpoint_rejects_a_bad_question(
    client: AsyncClient, body: dict[str, str]
) -> None:
    response = await client.post("/ask", json=body)

    assert response.status_code == 422


async def test_the_cost_of_a_priced_model_is_recorded_and_a_free_one_has_none(
    seeded: AsyncSession,
) -> None:
    class Priced(ScriptedAnswerer):
        name = "claude-sonnet-5-5"

    free = await run(seeded, ScriptedAnswerer("טענה [1]."))
    priced = await run(seeded, Priced("טענה [1]."))

    assert free.cost_usd is None
    assert priced.cost_usd == pytest.approx((10 * 2 + 5 * 10) / 1_000_000)
