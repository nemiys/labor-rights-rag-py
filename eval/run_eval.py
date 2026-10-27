"""Run the evaluation.

    uv run python eval/run_eval.py                      retrieval, on the dev questions
    uv run python eval/run_eval.py --generate           also answers (calls the model in .env)
    uv run python eval/run_eval.py --split test         the final run: do it once
    uv run python eval/run_eval.py --generate --condition all_laws
                                                        a comparison: closed_book or all_laws

Retrieval needs no model: it is free and can be repeated. Generation calls the answerer
chosen by ANSWERER, which can cost money or use a free tier's quota.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.embeddings.factory import make_embedder
from labor_rights_rag.evaluation.baselines import (
    ClosedBookAnswerer,
    ask_closed_book,
    load_all_hits,
)
from labor_rights_rag.evaluation.metrics import threshold_sweep
from labor_rights_rag.evaluation.questions import Question, load_questions
from labor_rights_rag.evaluation.report import answers_report, generation_report, retrieval_report
from labor_rights_rag.evaluation.runner import run_condition, run_generation, run_retrieval
from labor_rights_rag.generation.ask import AskResult, answer_from_hits
from labor_rights_rag.generation.factory import make_answerer
from labor_rights_rag.persistence.database import engine, session_factory
from labor_rights_rag.retrieval.bm25 import load_bm25_index
from labor_rights_rag.settings import settings

QUESTIONS = Path(__file__).parent / "questions.jsonl"
THRESHOLDS = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]


async def run(
    split: str,
    generate: bool,
    pause: float,
    out: Path | None,
    answers: Path | None,
    condition: str = "system",
) -> str:
    questions = [q for q in load_questions(QUESTIONS) if split == "all" or q.split == split]
    embedder = make_embedder(settings.embedder)
    async with session_factory() as session:
        if condition != "system":
            report = await run_comparison(session, questions, split, condition, pause, answers)
            await engine.dispose()
            if out:
                out.write_text(report, encoding="utf-8")
            return report

        bm25 = await load_bm25_index(session)
        rows, best = await run_retrieval(
            session, embedder, questions, bm25, settings.search_candidates, settings.rrf_k
        )
        answerable = [best[q.id] for q in questions if q.answerable]
        unanswerable = [best[q.id] for q in questions if not q.answerable]
        sweep = threshold_sweep(answerable, unanswerable, THRESHOLDS)
        report = retrieval_report(rows, sweep, split, settings.min_vector_score)

        if generate:
            answerer = make_answerer(settings.answerer)
            generated = await run_generation(
                session,
                embedder,
                answerer,
                questions,
                min_vector_score=settings.min_vector_score,
                pause_seconds=pause,
            )
            report += "\n" + generation_report(generated, answerer.name, split)
            if answers:
                answers.write_text(answers_report(generated, answerer.name), encoding="utf-8")
    await engine.dispose()
    if out:
        out.write_text(report, encoding="utf-8")
    return report


async def run_comparison(
    session: AsyncSession,
    questions: list[Question],
    split: str,
    condition: str,
    pause: float,
    answers: Path | None,
) -> str:
    """The same model and questions as the system, with no sources or with all of them."""
    if settings.answerer != "chat" or not settings.chat_model:
        raise SystemExit("the comparisons use the chat model of the system: set ANSWERER=chat")
    key = settings.chat_api_key.get_secret_value() if settings.chat_api_key else None
    if condition == "closed_book":
        closed = ClosedBookAnswerer(settings.chat_base_url, key, settings.chat_model)

        async def ask_one(question: str) -> AskResult:
            return await ask_closed_book(closed, question)

    else:
        answerer = make_answerer(settings.answerer)
        everything = await load_all_hits(session)
        print(f"all laws: {len(everything)} sources", file=sys.stderr, flush=True)

        async def ask_one(question: str) -> AskResult:
            return await answer_from_hits(session, answerer, question, everything)

    generated = await run_condition(ask_one, questions, pause)
    model = settings.chat_model
    if answers:
        answers.write_text(answers_report(generated, model), encoding="utf-8")
    return generation_report(generated, model, split, condition)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    parser.add_argument("--generate", action="store_true", help="also run the answers")
    parser.add_argument(
        "--condition",
        choices=["system", "closed_book", "all_laws"],
        default="system",
        help="system: the application. The others are comparisons (they imply --generate)",
    )
    parser.add_argument("--pause", type=float, default=12.0, help="seconds between model calls")
    parser.add_argument("--out", type=Path, help="write the report to this file")
    parser.add_argument("--answers", type=Path, help="write every answer in full, to read by hand")
    args = parser.parse_args()
    report = asyncio.run(
        run(args.split, args.generate, args.pause, args.out, args.answers, args.condition)
    )
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Hebrew on Windows
    print(report)


if __name__ == "__main__":
    main()
