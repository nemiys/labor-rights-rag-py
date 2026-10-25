"""GET /search: retrieval only, with scores. For debugging and for the evaluation.

The modes have the names they have in the evaluation (eval/run_eval.py). The default is
vector search: it was the best measured, see docs/adr/0010-retrieval-mode.md.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from labor_rights_rag.api.dependencies import Bm25Dep, EmbedderDep, SessionDep
from labor_rights_rag.retrieval.bm25 import bm25_search
from labor_rights_rag.retrieval.hit import Hit
from labor_rights_rag.retrieval.hybrid import hybrid_search
from labor_rights_rag.retrieval.text import text_search
from labor_rights_rag.retrieval.vector import vector_search
from labor_rights_rag.settings import settings

router = APIRouter()

Mode = Literal["vector", "text", "bm25", "hybrid", "hybrid_bm25"]


class SearchHit(BaseModel):
    rank: int
    score: float
    law: str
    law_id: int  # the Knesset id of the law
    section: str
    part: int  # 0 unless a long section was split
    text: str
    vector_rank: int | None = None  # hybrid only: the rank in each search, null if not found
    text_rank: int | None = None


class SearchResponse(BaseModel):
    query: str
    mode: Mode
    k: int
    hits: list[SearchHit]


@router.get("/search", response_model=SearchResponse)
async def search(
    session: SessionDep,
    embedder: EmbedderDep,
    bm25: Bm25Dep,
    q: Annotated[str, Query(min_length=1, description="the question")],
    mode: Annotated[
        Mode,
        Query(
            description="vector: by meaning (default). text: Postgres words. bm25: our BM25 "
            "words. hybrid / hybrid_bm25: meaning and words fused with RRF"
        ),
    ] = "vector",
    k: Annotated[int, Query(ge=1, le=50)] = 5,
    law: Annotated[int | None, Query(description="only this law, by its Knesset id")] = None,
) -> SearchResponse:
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="q must not be blank")

    if mode in ("bm25", "hybrid_bm25") and bm25 is None:
        raise HTTPException(status_code=503, detail="the BM25 index is not loaded")

    hits: list[Hit]
    if mode == "vector":
        hits = await vector_search(session, embedder, query, k, law)
    elif mode == "text":
        hits = await text_search(session, query, k, law)
    elif mode == "bm25":
        assert bm25 is not None  # checked above
        hits = await bm25_search(session, bm25, query, k, law)
    else:
        found = await hybrid_search(
            session,
            embedder,
            query,
            k,
            law,
            settings.search_candidates,
            settings.rrf_k,
            bm25 if mode == "hybrid_bm25" else None,
        )
        hits = found.hits
    return SearchResponse(
        query=query,
        mode=mode,
        k=k,
        hits=[
            SearchHit(
                rank=hit.rank,
                score=hit.score,
                law=hit.law_name,
                law_id=hit.law_odata_id,
                section=hit.section_number,
                part=hit.chunk_index,
                text=hit.text,
                vector_rank=hit.vector_rank,
                text_rank=hit.text_rank,
            )
            for hit in hits
        ],
    )
