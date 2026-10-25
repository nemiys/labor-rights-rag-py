"""Run the evaluation.

    uv run python eval/run_eval.py                      retrieval, on the dev questions
    uv run python eval/run_eval.py --generate           also answers (calls the model in .env)
    uv run python eval/run_eval.py --split test         the final run: do it once

Retrieval needs no model: it is free and can be repeated. Generation calls the answerer
chosen by ANSWERER, which can cost money or use a free tier's quota.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from labor_rights_rag.embeddings.factory import make_embedder
from labor_rights_rag.evaluation.metrics import threshold_sweep
from labor_rights_rag.evaluation.questions import load_questions
from labor_rights_rag.evaluation.report import generation_report, retrieval_report
from labor_rights_rag.evaluation.runner import run_generation, run_retrieval
from labor_rights_rag.generation.factory import make_answerer
from labor_rights_rag.persistence.database import engine, session_factory
from labor_rights_rag.retrieval.bm25 import load_bm25_index
from labor_rights_rag.settings import settings

QUESTIONS = Path(__file__).parent / "questions.jsonl"
THRESHOLDS = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]


async def run(split: str, generate: bool, pause: float, out: Path | None) -> str:
    questions = [q for q in load_questions(QUESTIONS) if split == "all" or q.split == split]
    embedder = make_embedder(settings.embedder)
    async with session_factory() as session:
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
    await engine.dispose()
    if out:
        out.write_text(report, encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    parser.add_argument("--generate", action="store_true", help="also run the answers")
    parser.add_argument("--pause", type=float, default=12.0, help="seconds between model calls")
    parser.add_argument("--out", type=Path, help="write the report to this file")
    args = parser.parse_args()
    report = asyncio.run(run(args.split, args.generate, args.pause, args.out))
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Hebrew on Windows
    print(report)


if __name__ == "__main__":
    main()
