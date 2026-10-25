"""Runs the questions through the system and collects what is needed for the measures."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.embeddings.base import Embedder
from labor_rights_rag.evaluation.metrics import (
    facts_found,
    first_relevant_rank,
    hit_at,
    recall_at,
    reciprocal_rank,
)
from labor_rights_rag.evaluation.questions import Question
from labor_rights_rag.generation.ask import AskResult, ask
from labor_rights_rag.generation.base import Answerer
from labor_rights_rag.retrieval.bm25 import Bm25Index, bm25_search
from labor_rights_rag.retrieval.hit import Hit
from labor_rights_rag.retrieval.hybrid import hybrid_search
from labor_rights_rag.retrieval.text import text_search
from labor_rights_rag.retrieval.vector import vector_search

MODES = ("vector", "text", "bm25", "hybrid", "hybrid_bm25")
DEPTH = 10  # how many chunks are looked at: MRR is measured within this depth


@dataclass(frozen=True)
class RetrievalRow:
    question: Question
    mode: str
    rank: int | None  # of the first chunk from an expected section
    recall5: float


@dataclass(frozen=True)
class RetrievalSummary:
    n: int
    hit1: float
    hit3: float
    hit5: float
    mrr: float
    recall5: float


def summarize_retrieval(rows: Sequence[RetrievalRow]) -> RetrievalSummary:
    n = len(rows)
    if n == 0:
        return RetrievalSummary(0, 0, 0, 0, 0, 0)
    return RetrievalSummary(
        n,
        sum(hit_at(r.rank, 1) for r in rows) / n,
        sum(hit_at(r.rank, 3) for r in rows) / n,
        sum(hit_at(r.rank, 5) for r in rows) / n,
        sum(reciprocal_rank(r.rank, DEPTH) for r in rows) / n,
        sum(r.recall5 for r in rows) / n,
    )


async def _search(
    session: AsyncSession,
    embedder: Embedder,
    bm25: Bm25Index,
    mode: str,
    question: str,
    candidates: int,
    rrf_k: int,
) -> list[Hit]:
    if mode == "vector":
        return await vector_search(session, embedder, question, DEPTH)
    if mode == "text":
        return await text_search(session, question, DEPTH)
    if mode == "bm25":
        return await bm25_search(session, bm25, question, DEPTH)
    index = bm25 if mode == "hybrid_bm25" else None
    found = await hybrid_search(session, embedder, question, DEPTH, None, candidates, rrf_k, index)
    return found.hits


async def run_retrieval(
    session: AsyncSession,
    embedder: Embedder,
    questions: Sequence[Question],
    bm25: Bm25Index,
    candidates: int = 50,
    rrf_k: int = 60,
) -> tuple[list[RetrievalRow], dict[str, float]]:
    """Retrieval rows for the answerable questions in every mode, and, for every question, the
    similarity of its closest chunk (what the refusal threshold is compared with)."""
    rows: list[RetrievalRow] = []
    best_scores: dict[str, float] = {}
    for question in questions:
        top = await vector_search(session, embedder, question.question, 1)
        best_scores[question.id] = top[0].score if top else 0.0
        if not question.answerable:
            continue
        for mode in MODES:
            hits = await _search(
                session, embedder, bm25, mode, question.question, candidates, rrf_k
            )
            rows.append(
                RetrievalRow(
                    question,
                    mode,
                    first_relevant_rank(hits, question),
                    recall_at(hits, question, 5),
                )
            )
    return rows, best_scores


@dataclass(frozen=True)
class GenerationRow:
    question: Question
    result: AskResult | None  # None when the call failed
    error: str | None

    @property
    def answered(self) -> bool:
        return self.result is not None and self.result.status == "answered"

    @property
    def facts_ok(self) -> bool:
        return self.answered and facts_found(
            self.result.answer if self.result else "", self.question.expected_facts
        )

    @property
    def citation_ok(self) -> bool:
        if not (self.answered and self.result):
            return False
        return any(
            self.question.is_expected(c.card.law_id, c.card.section) for c in self.result.citations
        )


async def run_generation(
    session: AsyncSession,
    embedder: Embedder,
    answerer: Answerer,
    questions: Sequence[Question],
    *,
    min_vector_score: float,
    pause_seconds: float = 0.0,
) -> list[GenerationRow]:
    rows: list[GenerationRow] = []
    for question in questions:
        try:
            result = await ask(
                session,
                embedder,
                answerer,
                question.question,
                k=5,
                min_vector_score=min_vector_score,
            )
            rows.append(GenerationRow(question, result, None))
        except Exception as error:  # a failed call is a result, not the end of the run
            rows.append(GenerationRow(question, None, f"{type(error).__name__}: {error}"[:200]))
        await asyncio.sleep(pause_seconds)
    return rows
