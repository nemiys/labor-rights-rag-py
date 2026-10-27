"""From a question to a checked answer: search, decide, ask the model, verify, build cards."""

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.embeddings.base import Embedder
from labor_rights_rag.generation.base import Answerer
from labor_rights_rag.generation.card import VerificationCard, build_card
from labor_rights_rag.generation.messages import DISCLAIMER, REFUSAL_MESSAGE
from labor_rights_rag.generation.parse import parse_answer
from labor_rights_rag.generation.pricing import estimate_cost_usd
from labor_rights_rag.persistence.models import Law
from labor_rights_rag.retrieval.hit import Hit
from labor_rights_rag.retrieval.vector import vector_search

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
    cost_usd: float | None = None  # None for a model that is free or not in the price list
    disclaimer: str = DISCLAIMER


def _refusal(status: Status, model: str | None = None, **usage: float) -> AskResult:
    input_tokens = int(usage.get("input_tokens", 0))
    output_tokens = int(usage.get("output_tokens", 0))
    return AskResult(
        status=status,
        answer=REFUSAL_MESSAGE,
        citations=[],
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        seconds=float(usage.get("seconds", 0.0)),
        cost_usd=estimate_cost_usd(model, input_tokens, output_tokens),
    )


async def ask(
    session: AsyncSession,
    embedder: Embedder,
    answerer: Answerer,
    question: str,
    *,
    k: int,
    min_vector_score: float,
    law_odata_id: int | None = None,
) -> AskResult:
    # Vector search alone: it was as good as every combination that was measured (ADR-0010).
    hits = await vector_search(session, embedder, question, k, law_odata_id)
    if not hits or hits[0].score < min_vector_score:
        return _refusal("refused_low_score")
    return await answer_from_hits(session, answerer, question, hits)


async def answer_from_hits(
    session: AsyncSession, answerer: Answerer, question: str, hits: Sequence[Hit]
) -> AskResult:
    """Ask the model with these sources and check what it wrote. The evaluation also uses it
    with sources it chose itself (all the laws), so that every condition is checked alike."""
    response = await answerer.answer(question, hits)
    usage = {
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "seconds": response.seconds,
    }
    parsed = parse_answer(response.text, len(hits))
    if parsed.refused:
        return _refusal("refused_by_model", response.model, **usage)
    if parsed.invalid_citations:
        return _refusal("rejected_invalid_citations", response.model, **usage)
    if not parsed.citations:
        return _refusal("rejected_no_citations", response.model, **usage)

    cited = [(number, hits[number - 1]) for number in parsed.citations]
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
        cost_usd=estimate_cost_usd(response.model, response.input_tokens, response.output_tokens),
    )
