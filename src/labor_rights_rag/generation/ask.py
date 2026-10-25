"""From a question to a checked answer: search, decide, ask the model, verify, build cards."""

from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.embeddings.base import Embedder
from labor_rights_rag.generation.base import Answerer
from labor_rights_rag.generation.card import VerificationCard, build_card
from labor_rights_rag.generation.messages import DISCLAIMER, REFUSAL_MESSAGE
from labor_rights_rag.generation.parse import parse_answer
from labor_rights_rag.persistence.models import Law
from labor_rights_rag.retrieval.hybrid import hybrid_search

# Why a reply is what it is. The person sees only the answer or the refusal sentence; the
# status is for the logs and for the evaluation.
Status = Literal[
    "answered",
    "refused_low_score",  # nothing close enough: the model was not called
    "refused_by_model",  # the sources do not answer
    "rejected_invalid_citations",  # the model cited a source that was never given
    "rejected_no_citations",  # an answer with no source is not allowed
]


class Citation(BaseModel):
    number: int  # the [n] in the answer
    card: VerificationCard


class AskResult(BaseModel):
    status: Status
    answer: str
    citations: list[Citation]
    model: str | None  # None when the model was not called
    input_tokens: int
    output_tokens: int
    seconds: float
    disclaimer: str = DISCLAIMER


def _refusal(status: Status, model: str | None = None, **usage: float) -> AskResult:
    return AskResult(
        status=status,
        answer=REFUSAL_MESSAGE,
        citations=[],
        model=model,
        input_tokens=int(usage.get("input_tokens", 0)),
        output_tokens=int(usage.get("output_tokens", 0)),
        seconds=float(usage.get("seconds", 0.0)),
    )


async def ask(
    session: AsyncSession,
    embedder: Embedder,
    answerer: Answerer,
    question: str,
    *,
    k: int,
    candidates: int,
    rrf_k: int,
    min_vector_score: float,
    law_odata_id: int | None = None,
) -> AskResult:
    found = await hybrid_search(session, embedder, question, k, law_odata_id, candidates, rrf_k)
    if found.best_vector_score is None or found.best_vector_score < min_vector_score:
        return _refusal("refused_low_score")

    response = await answerer.answer(question, found.hits)
    usage = {
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "seconds": response.seconds,
    }
    parsed = parse_answer(response.text, len(found.hits))
    if parsed.refused:
        return _refusal("refused_by_model", response.model, **usage)
    if parsed.invalid_citations:
        return _refusal("rejected_invalid_citations", response.model, **usage)
    if not parsed.citations:
        return _refusal("rejected_no_citations", response.model, **usage)

    cited = [(number, found.hits[number - 1]) for number in parsed.citations]
    laws = await session.scalars(
        select(Law).where(Law.odata_id.in_({hit.law_odata_id for _, hit in cited}))
    )
    by_id = {law.odata_id: law for law in laws}
    return AskResult(
        status="answered",
        answer=parsed.text,
        citations=[
            Citation(number=number, card=build_card(hit, by_id[hit.law_odata_id]))
            for number, hit in cited
        ],
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        seconds=response.seconds,
    )
