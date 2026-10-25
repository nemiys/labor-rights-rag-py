"""A search result, the same for every kind of search."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Hit:
    rank: int  # 1 is the best
    # Vector search: cosine similarity (higher is closer). Text search: ts_rank_cd. The two
    # are on different scales, so only the rank can be compared across searches. For debugging.
    score: float
    chunk_id: int
    law_odata_id: int
    law_name: str
    section_number: str
    chunk_index: int
    text: str
