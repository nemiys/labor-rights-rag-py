"""POST /ask: a question in, a checked answer with verification cards out."""

import logging
from typing import Annotated

import anthropic
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from labor_rights_rag.api.dependencies import AnswererDep, EmbedderDep, SessionDep
from labor_rights_rag.api.rate_limit import limit_ask
from labor_rights_rag.generation.ask import AskResult, ask
from labor_rights_rag.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()

SOURCES_FOR_THE_ANSWER = 5  # how many sections the model reads

# What the answer model's clients raise when the service is down, busy or refuses the key,
# after their own retries.
MODEL_UNAVAILABLE = (httpx.HTTPError, anthropic.APIError, TimeoutError)


class AskRequest(BaseModel):
    question: Annotated[str, Field(min_length=1, max_length=1000)]


@router.post(
    "/ask",
    response_model=AskResult,
    dependencies=[Depends(limit_ask)],
    responses={
        429: {"description": "Too many questions from this address; see Retry-After"},
        503: {"description": "The answer model is not available right now; see Retry-After"},
    },
)
async def post_ask(
    body: AskRequest, session: SessionDep, embedder: EmbedderDep, answerer: AnswererDep
) -> AskResult:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question must not be blank")
    try:
        return await ask(
            session,
            embedder,
            answerer,
            question,
            k=SOURCES_FOR_THE_ANSWER,
            min_vector_score=settings.min_vector_score,
        )
    except MODEL_UNAVAILABLE:
        # The cause goes to the log; the person gets a clear "try again later".
        logger.exception("The answer model could not be reached")
        raise HTTPException(
            status_code=503,
            detail="The answer model is not available right now",
            headers={"Retry-After": "30"},
        ) from None
