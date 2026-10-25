"""GET /search: retrieval only, with scores. For debugging and for the evaluation."""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from labor_rights_rag.api.dependencies import EmbedderDep, SessionDep
from labor_rights_rag.retrieval.vector import vector_search

router = APIRouter()


class SearchHit(BaseModel):
    rank: int
    score: float
    law: str
    law_id: int  # the Knesset id of the law
    section: str
    part: int  # 0 unless a long section was split
    text: str


class SearchResponse(BaseModel):
    query: str
    mode: Literal["vector"]
    k: int
    hits: list[SearchHit]


@router.get("/search", response_model=SearchResponse)
async def search(
    session: SessionDep,
    embedder: EmbedderDep,
    q: Annotated[str, Query(min_length=1, description="the question")],
    mode: Literal["vector"] = "vector",
    k: Annotated[int, Query(ge=1, le=50)] = 5,
    law: Annotated[int | None, Query(description="only this law, by its Knesset id")] = None,
) -> SearchResponse:
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="q must not be blank")

    hits = await vector_search(session, embedder, query, k, law)
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
            )
            for hit in hits
        ],
    )
