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
    # Hybrid search only: the rank this chunk had in each search, empty if it did not find it.
    vector_rank: int | None = None
    text_rank: int | None = None
    # The cosine similarity from the vector search, kept through the fusion: it is the one
    # score that says how close the chunk is to the question. None if only words found it.
    vector_score: float | None = None
