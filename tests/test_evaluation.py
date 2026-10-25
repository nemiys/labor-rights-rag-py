import hashlib
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.embeddings.fake import HashEmbedder
from labor_rights_rag.evaluation.metrics import (
    facts_found,
    first_relevant_rank,
    hit_at,
    recall_at,
    reciprocal_rank,
    threshold_sweep,
)
from labor_rights_rag.evaluation.questions import ExpectedSection, Question, load_questions
from labor_rights_rag.evaluation.report import generation_report, retrieval_report
from labor_rights_rag.evaluation.runner import (
    GenerationRow,
    run_generation,
    run_retrieval,
    summarize_retrieval,
)
from labor_rights_rag.generation.ask import AskResult
from labor_rights_rag.generation.fake import FakeAnswerer
from labor_rights_rag.persistence.models import Chunk, Law
from labor_rights_rag.retrieval.bm25 import Bm25Index
from labor_rights_rag.retrieval.hit import Hit
from labor_rights_rag.retrieval.normalize import to_search_text

EVAL = Path(__file__).parent.parent / "eval"


def hit(rank: int, law: int, section: str) -> Hit:
    return Hit(rank, 0.5, rank, law, "חוק", section, 0, "טקסט")


def question(*expected: tuple[int, str], answerable: bool = True, **extra: object) -> Question:
    return Question(
        id="q",
        split="dev",
        category="paraphrase",
        question="שאלה",
        answerable=answerable,
        expected=[ExpectedSection(law=law, section=section) for law, section in expected],
        **extra,
    )


# The measures


def test_the_rank_is_that_of_the_first_chunk_from_an_expected_section() -> None:
    hits = [hit(1, 10, "1"), hit(2, 10, "3"), hit(3, 11, "3")]

    assert first_relevant_rank(hits, question((10, "3"))) == 2
    assert first_relevant_rank(hits, question((11, "3"))) == 3  # the law counts too
    assert first_relevant_rank(hits, question((10, "9"))) is None


def test_hit_at_k_and_reciprocal_rank() -> None:
    assert hit_at(3, 3) and not hit_at(4, 3) and not hit_at(None, 5)
    assert reciprocal_rank(4, 10) == 0.25
    assert reciprocal_rank(11, 10) == 0.0  # beyond the depth
    assert reciprocal_rank(None, 10) == 0.0


def test_recall_is_the_share_of_expected_sections_in_the_first_k() -> None:
    hits = [hit(1, 10, "1"), hit(2, 10, "2"), hit(3, 10, "9")]
    wanted = question((10, "1"), (10, "9"), (10, "5"))

    assert recall_at(hits, wanted, 2) == pytest.approx(1 / 3)
    assert recall_at(hits, wanted, 3) == pytest.approx(2 / 3)


def test_a_fact_counts_when_any_of_its_phrasings_is_in_the_answer() -> None:
    answer = "המעסיק חייב לשלם עשרים ושישה שבועות, כלומר פיצוי."

    assert facts_found(answer, [["26", "עשרים ושישה"], ["פיצוי"]])
    assert not facts_found(answer, [["26", "עשרים ושישה"], ["קנס"]])
    assert facts_found(answer, [])  # no facts to check


def test_facts_are_compared_without_quotation_marks_or_points() -> None:
    assert facts_found('לפי חוק התשי"א', [["התשי״א"]])
    assert facts_found("שבעה־עשר", [["שבעה עשר"]])


def test_threshold_sweep_shows_both_errors_of_each_threshold() -> None:
    rows = threshold_sweep([0.7, 0.6, 0.5], [0.55, 0.4], [0.45, 0.58])

    assert (rows[0].false_refusals, rows[0].answered_without_source) == (0.0, 0.5)
    assert rows[1].false_refusals == pytest.approx(1 / 3)
    assert rows[1].answered_without_source == 0.0


# The question file


def test_the_questions_file_is_well_formed() -> None:
    questions = load_questions(EVAL / "questions.jsonl")

    assert len({q.id for q in questions}) == len(questions)
    assert {q.split for q in questions} == {"dev", "test"}
    assert sum(not q.answerable for q in questions) >= 5
    for q in questions:
        assert q.answerable == bool(q.expected), q.id
        if not q.answerable:
            assert q.expected_facts == [], q.id


def test_the_questions_file_is_frozen() -> None:
    recorded = (EVAL / "QUESTIONS.sha256").read_text().strip()
    # Windows may check the file out with CRLF endings; the hash is of the LF form.
    content = (EVAL / "questions.jsonl").read_bytes().replace(b"\r\n", b"\n")
    actual = hashlib.sha256(content).hexdigest()

    # If this fails the evaluation set was changed. Do it on purpose: update the hash and say
    # in the commit why.
    assert actual == recorded


# Running it (a database with a small law that no real question can reach)

LAW = 999012
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
async def seeded(db_session: AsyncSession) -> AsyncSession:
    db_session.add(
        Law(
            odata_id=LAW,
            name="חוק לבדיקה",
            wikisource_title="חוק לבדיקה",
            chunks=[
                _chunk("1", "קלמרפוז טורבינה מגיעה לעובד בכל שנה"),
                _chunk("2", "זמזמוז אחר לגמרי"),
            ],
        )
    )
    await db_session.flush()
    return db_session


def _q(qid: str, text: str, section: str | None) -> Question:
    return Question(
        id=qid,
        split="dev",
        category="paraphrase",
        question=text,
        answerable=section is not None,
        expected=[ExpectedSection(law=LAW, section=section)] if section else [],
    )


async def test_retrieval_run_ranks_the_expected_section_in_every_mode(
    seeded: AsyncSession,
) -> None:
    questions = [_q("a", "קלמרפוז טורבינה", "1"), _q("b", "משהו שאין לו תשובה", None)]

    chunks = await seeded.execute(
        select(Chunk.id, Chunk.search_text)
        .join(Law, Chunk.law_id == Law.id)
        .where(Law.odata_id == LAW)
    )
    index = Bm25Index((row.id, LAW, row.search_text or "") for row in chunks)
    rows, best = await run_retrieval(seeded, embedder, questions, index)

    assert {r.mode for r in rows} == {"vector", "text", "bm25", "hybrid", "hybrid_bm25"}
    assert all(r.question.id == "a" for r in rows)  # no rows for unanswerable questions
    assert all(r.rank == 1 for r in rows)
    assert set(best) == {"a", "b"}  # but every question has its closest-chunk score
    summary = summarize_retrieval([r for r in rows if r.mode == "hybrid"])
    assert (summary.hit1, summary.mrr) == (1.0, 1.0)


async def test_generation_run_records_each_question_and_survives_a_failed_call(
    seeded: AsyncSession,
) -> None:
    class Flaky(FakeAnswerer):
        calls = 0

        async def answer(self, question: str, hits):  # type: ignore[no-untyped-def]
            Flaky.calls += 1
            if Flaky.calls == 1:
                raise RuntimeError("boom")
            return await super().answer(question, hits)

    questions = [_q("a", "קלמרפוז טורבינה", "1"), _q("b", "קלמרפוז טורבינה", "1")]

    rows = await run_generation(seeded, embedder, Flaky(), questions, min_vector_score=0.0)

    assert rows[0].result is None and "boom" in (rows[0].error or "")
    assert rows[1].result is not None and rows[1].result.status == "answered"


# The reports


def test_reports_have_the_tables_and_the_misses() -> None:
    rows_q = _q("a", "קלמרפוז", "1")
    from labor_rights_rag.evaluation.runner import RetrievalRow

    rows = [
        RetrievalRow(rows_q, m, 7 if m == "text" else 1, 1.0) for m in ("vector", "text", "hybrid")
    ]
    sweep = threshold_sweep([0.7], [0.4], [0.5])

    report = retrieval_report(rows, sweep, "dev", 0.5)

    assert "| hybrid | 100% | 100% | 100% | 1.000 | 100% |" in report
    assert "| text | 0% | 0% | 0% | 0.143 | 100% |" in report
    assert "| 0.50 | 0% | 0% |" in report


def test_generation_report_counts_refusals_and_lists_the_failures() -> None:
    good = _q("a", "שאלה", "1")
    unanswerable = _q("b", "שאלה", None)

    def result(status: str) -> AskResult:
        return AskResult(
            status=status,
            answer="טקסט",
            citations=[],
            model="m",
            input_tokens=10,
            output_tokens=5,
            seconds=1.0,
        )

    rows = [
        GenerationRow(good, result("refused_by_model"), None),
        GenerationRow(unanswerable, result("refused_by_model"), None),
        GenerationRow(unanswerable, None, "ReadTimeout"),
    ]

    report = generation_report(rows, "m", "dev")

    assert "| Answerable questions answered | 0% (0/1) |" in report
    assert "| Unanswerable questions refused | 100% (1/1) |" in report
    assert "| a | refused_by_model |" in report  # the failure is listed
    assert "Calls that failed: 1" in report


def test_answers_report_has_each_answer_in_full_with_what_it_cites() -> None:
    from labor_rights_rag.evaluation.report import answers_report
    from labor_rights_rag.generation.ask import Citation
    from labor_rights_rag.generation.card import VerificationCard

    card = VerificationCard(
        law="חוק", law_id=LAW, section="1", part=0, quote="הטקסט השמור של הסעיף",
        text_as_of=None, currency_status="ok", currency_warning=None, knesset_url="u",
        wikisource_url="w", last_amendment=None, last_amendment_url=None,
        search_hint="h", disclaimer="d",
    )  # fmt: skip
    answered = AskResult(
        status="answered", answer="התשובה המלאה [1]", citations=[Citation(number=1, card=card)],
        model="m", input_tokens=1, output_tokens=1, seconds=1.0,
    )  # fmt: skip
    rows = [
        GenerationRow(_q("a", "שאלה ראשונה", "1"), answered, None),
        GenerationRow(_q("b", "שאלה שנייה", None), None, "ReadTimeout"),
    ]

    report = answers_report(rows, "m")

    assert "**Question:** שאלה ראשונה" in report
    assert "**Answer:** התשובה המלאה [1]" in report
    assert f"- [1] {LAW}:1: הטקסט השמור של הסעיף" in report
    assert "**Call failed:** ReadTimeout" in report
    assert "none (not answerable)" in report


async def test_a_question_that_hangs_is_cut_off_and_the_run_goes_on(seeded: AsyncSession) -> None:
    import asyncio

    class Hangs(FakeAnswerer):
        calls = 0

        async def answer(self, question: str, hits):  # type: ignore[no-untyped-def]
            Hangs.calls += 1
            if Hangs.calls == 1:
                await asyncio.sleep(30)
            return await super().answer(question, hits)

    questions = [_q("a", "קלמרפוז טורבינה", "1"), _q("b", "קלמרפוז טורבינה", "1")]

    rows = await run_generation(
        seeded, embedder, Hangs(), questions, min_vector_score=0.0, question_timeout=0.2
    )

    assert rows[0].result is None and "TimeoutError" in (rows[0].error or "")
    assert rows[1].result is not None and rows[1].result.status == "answered"
