"""POST /ask: a question in, a checked answer with verification cards out."""

from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from labor_rights_rag.api.dependencies import AnswererDep, EmbedderDep, SessionDep
from labor_rights_rag.generation.ask import AskResult, ask
from labor_rights_rag.settings import settings

router = APIRouter()

SOURCES_FOR_THE_ANSWER = 5  # how many sections the model reads


class AskRequest(BaseModel):
    question: Annotated[str, Field(min_length=1, max_length=1000)]


@router.post("/ask", response_model=AskResult)
async def post_ask(
    body: AskRequest, session: SessionDep, embedder: EmbedderDep, answerer: AnswererDep
) -> AskResult:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question must not be blank")
    return await ask(
        session,
        embedder,
        answerer,
        question,
        k=SOURCES_FOR_THE_ANSWER,
        candidates=settings.search_candidates,
        rrf_k=settings.rrf_k,
        min_vector_score=settings.min_vector_score,
    )
