"""Hybrid search: vector and text search combined with Reciprocal Rank Fusion (ADR-0007)."""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.embeddings.base import Embedder
from labor_rights_rag.retrieval.hit import Hit
from labor_rights_rag.retrieval.text import text_search
from labor_rights_rag.retrieval.vector import vector_search


@dataclass(frozen=True)
class SearchResult:
    hits: list[Hit]
    # The closeness of the best chunk by meaning, among all the candidates (not only the
    # final hits). The decision to refuse before the model reads this. None if nothing was found.
    best_vector_score: float | None


def reciprocal_rank_fusion(vector: Sequence[Hit], text: Sequence[Hit], k: int = 60) -> list[Hit]:
    """One ranked list from two. A chunk scores 1 / (k + rank) in each list that has it.

    Only the ranks count, never the scores: the two searches score on different scales.
    """
    found: dict[int, Hit] = {}
    scores: dict[int, float] = {}
    vector_ranks: dict[int, int] = {}
    text_ranks: dict[int, int] = {}
    vector_scores = {hit.chunk_id: hit.score for hit in vector}
    for ranks, hits in ((vector_ranks, vector), (text_ranks, text)):
        for position, hit in enumerate(hits, start=1):
            found.setdefault(hit.chunk_id, hit)
            ranks[hit.chunk_id] = position
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1 / (k + position)

    def order(chunk_id: int) -> tuple[float, int, int]:
        best_rank = min(
            vector_ranks.get(chunk_id, len(found)), text_ranks.get(chunk_id, len(found))
        )
        # Highest score first; a tie goes to the better single rank, then to the lower id.
        return (-scores[chunk_id], best_rank, chunk_id)

    return [
        replace(
            found[chunk_id],
            rank=position,
            score=scores[chunk_id],
            vector_rank=vector_ranks.get(chunk_id),
            text_rank=text_ranks.get(chunk_id),
            vector_score=vector_scores.get(chunk_id),
        )
        for position, chunk_id in enumerate(sorted(found, key=order), start=1)
    ]


async def hybrid_search(
    session: AsyncSession,
    embedder: Embedder,
    query: str,
    k: int,
    law_odata_id: int | None = None,
    candidates: int = 50,
    rrf_k: int = 60,
) -> SearchResult:
    # More candidates than the caller wants: a chunk that both searches put in the middle
    # can still win. The two queries run one after the other on the same session.
    depth = max(candidates, k)
    by_meaning = await vector_search(session, embedder, query, depth, law_odata_id)
    by_words = await text_search(session, query, depth, law_odata_id)
    fused = reciprocal_rank_fusion(by_meaning, by_words, rrf_k)[:k]
    return SearchResult(fused, by_meaning[0].score if by_meaning else None)
