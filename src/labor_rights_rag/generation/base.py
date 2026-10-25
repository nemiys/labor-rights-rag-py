"""The interface of a model that writes the answer: nothing else knows which one runs."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from labor_rights_rag.retrieval.hit import Hit


@dataclass(frozen=True)
class ModelResponse:
    text: str  # what the model wrote, with its [1] markers: not yet checked
    model: str
    input_tokens: int  # for the cost record; 0 where the model does not report it
    output_tokens: int
    seconds: float


class Answerer(Protocol):
    name: str  # stored with every answer, to compare models in the evaluation

    async def answer(self, question: str, hits: Sequence[Hit]) -> ModelResponse:
        """Write an answer to the question from the hits and nothing else."""
        ...
