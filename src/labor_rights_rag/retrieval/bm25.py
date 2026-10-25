"""Word search ranked by BM25, written by hand.

Postgres full-text ranking treats every word of the question alike, so a rare word such as
"14א" loses to common ones such as "שכר". BM25 scores a chunk by the words of the question
it holds, each weighted by:
  - rarity: a word in few chunks is worth much, a word in nearly all chunks, almost nothing;
  - saturation: the tenth time a word appears adds far less than the first;
  - length: a long chunk holds many words anyway, so a match there counts for less.
The index lives in memory: the corpus is a closed list of about a thousand chunks.
"""

import math
from collections import Counter
from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.persistence.models import Chunk, Law
from labor_rights_rag.retrieval.hit import Hit
from labor_rights_rag.retrieval.normalize import query_terms


class Bm25Index:
    def __init__(
        self, rows: Iterable[tuple[int, int, str]], k1: float = 1.2, b: float = 0.75
    ) -> None:
        """`rows` are (chunk id, the law's Knesset id, the normalized text of the chunk)."""
        self._k1 = k1
        self._b = b
        self._counts: dict[int, Counter[str]] = {}
        self._law: dict[int, int] = {}
        for chunk_id, law_id, text in rows:
            self._counts[chunk_id] = Counter(text.split())
            self._law[chunk_id] = law_id
        self._length = {chunk_id: sum(c.values()) for chunk_id, c in self._counts.items()}
        self._average = sum(self._length.values()) / len(self._length) if self._length else 0.0
        self._chunks_with: Counter[str] = Counter()
        for counts in self._counts.values():
            self._chunks_with.update(counts.keys())

    def __len__(self) -> int:
        return len(self._counts)

    def _rarity(self, term: str) -> float:
        containing = self._chunks_with[term]
        return math.log(1 + (len(self) - containing + 0.5) / (containing + 0.5))

    def top(
        self, terms: Sequence[str], limit: int, law_odata_id: int | None = None
    ) -> list[tuple[int, float]]:
        """The best chunks as (chunk id, score), best first; equal scores by chunk id."""
        scored: list[tuple[int, float]] = []
        for chunk_id, counts in self._counts.items():
            if law_odata_id is not None and self._law[chunk_id] != law_odata_id:
                continue
            length_factor = 1 - self._b + self._b * self._length[chunk_id] / self._average
            score = 0.0
            for term in terms:
                frequency = counts.get(term, 0)
                if frequency:
                    saturation = frequency * (self._k1 + 1) / (frequency + self._k1 * length_factor)
                    score += self._rarity(term) * saturation
            if score > 0:
                scored.append((chunk_id, score))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:limit]


async def load_bm25_index(session: AsyncSession) -> Bm25Index:
    """Build the index from every chunk in the database. Build it again after an ingest."""
    rows = await session.execute(
        select(Chunk.id, Law.odata_id, Chunk.search_text)
        .join(Law, Chunk.law_id == Law.id)
        .where(Chunk.search_text.is_not(None))
    )
    return Bm25Index((row.id, row.odata_id, row.search_text) for row in rows)


async def bm25_search(
    session: AsyncSession,
    index: Bm25Index,
    query: str,
    k: int,
    law_odata_id: int | None = None,
) -> list[Hit]:
    terms = query_terms(query)
    best = index.top(terms, k, law_odata_id)
    if not best:
        return []
    rows = await session.execute(
        select(
            Chunk.id,
            Law.odata_id,
            Law.name,
            Chunk.section_number,
            Chunk.chunk_index,
            Chunk.text,
        )
        .join(Law, Chunk.law_id == Law.id)
        .where(Chunk.id.in_([chunk_id for chunk_id, _ in best]))
    )
    by_id = {row.id: row for row in rows}
    return [
        Hit(
            rank=position,
            score=score,
            chunk_id=chunk_id,
            law_odata_id=by_id[chunk_id].odata_id,
            law_name=by_id[chunk_id].name,
            section_number=by_id[chunk_id].section_number,
            chunk_index=by_id[chunk_id].chunk_index,
            text=by_id[chunk_id].text,
        )
        for position, (chunk_id, score) in enumerate(best, start=1)
    ]
