"""A deterministic stand-in for tests: no model, no network, no cost."""

from collections.abc import Sequence

from labor_rights_rag.generation.base import ModelResponse
from labor_rights_rag.generation.prompt import NO_ANSWER_MARKER
from labor_rights_rag.retrieval.hit import Hit


class FakeAnswerer:
    name = "fake"

    async def answer(self, question: str, hits: Sequence[Hit]) -> ModelResponse:
        # It understands nothing: it repeats the start of the first source and cites it.
        text = f"{hits[0].text[:80]} [1]" if hits else NO_ANSWER_MARKER
        return ModelResponse(text, self.name, input_tokens=0, output_tokens=0, seconds=0.0)
