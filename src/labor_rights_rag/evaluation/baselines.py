"""The two comparison conditions for the answers: no retrieval, and all the laws in the prompt.

The system gives the model the few sections it found. To say whether that retrieval helps,
the same model gets the same questions with nothing (it answers from what it remembers) and
with everything (all the chunks of the corpus as numbered sources).
"""

from collections.abc import Sequence
from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from labor_rights_rag.generation.ask import AskResult
from labor_rights_rag.generation.base import Answerer, ModelResponse
from labor_rights_rag.generation.chat_completions import ChatCompletionsAnswerer
from labor_rights_rag.generation.messages import REFUSAL_MESSAGE
from labor_rights_rag.generation.prompt import NO_ANSWER_MARKER, Prompt
from labor_rights_rag.persistence.models import Chunk, Law
from labor_rights_rag.retrieval.hit import Hit

CLOSED_BOOK_SYSTEM_PROMPT = f"""You answer questions about Israeli labor law for ordinary \
people, from what you know. You are given no documents.

Rules:
1. Write in simple Hebrew, in short sentences, as if explaining to a person with no legal \
background.
2. Name the law and the section when you know them.
3. If you do not know, or the question is not about employment rights in Israeli law, reply \
with exactly {NO_ANSWER_MARKER} and nothing else.
4. Do not give legal advice. Describe what the law says."""


class ClosedBookAnswerer(ChatCompletionsAnswerer):
    """The same client and model as the system, but the prompt has no sources."""

    def _prompt(self, question: str, hits: Sequence[Hit]) -> Prompt:
        return Prompt(CLOSED_BOOK_SYSTEM_PROMPT, f"<question>\n{escape(question)}\n</question>")


async def ask_closed_book(answerer: Answerer, question: str) -> AskResult:
    """No sources, so there is nothing to cite and nothing to check: the answer is what the
    model wrote, unless it said it does not know."""
    response: ModelResponse = await answerer.answer(question, [])
    text = response.text.strip()
    refused = not text or text.startswith(NO_ANSWER_MARKER)
    return AskResult(
        status="refused_by_model" if refused else "answered",
        answer=REFUSAL_MESSAGE if refused else text.replace(NO_ANSWER_MARKER, "").strip(),
        citations=[],
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        seconds=response.seconds,
    )


async def load_all_hits(session: AsyncSession) -> list[Hit]:
    """Every chunk of the corpus as a hit, in the order of the laws and their sections."""
    rows = await session.execute(
        select(Chunk, Law).join(Law, Chunk.law_id == Law.id).order_by(Law.odata_id, Chunk.id)
    )
    return [
        Hit(
            rank=number,
            score=0.0,
            chunk_id=chunk.id,
            law_odata_id=law.odata_id,
            law_name=law.name,
            section_number=chunk.section_number,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
        )
        for number, (chunk, law) in enumerate(rows.all(), start=1)
    ]
