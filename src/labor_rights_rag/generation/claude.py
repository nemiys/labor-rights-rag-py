"""The answer written by Claude, through the official SDK."""

import time
from collections.abc import Sequence
from typing import Literal

from anthropic import AsyncAnthropic

from labor_rights_rag.generation.base import ModelResponse
from labor_rights_rag.generation.prompt import build_prompt
from labor_rights_rag.retrieval.hit import Hit

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class ClaudeAnswerer:
    def __init__(
        self,
        api_key: str,
        model: str,
        effort: Effort = "low",
        max_tokens: int = 4000,
        client: AsyncAnthropic | None = None,
    ) -> None:
        self.name = model
        self._effort = effort
        self._max_tokens = max_tokens
        # The SDK retries connection errors, 429 and 5xx by itself (twice by default).
        self._client = client or AsyncAnthropic(api_key=api_key, timeout=60.0)

    async def answer(self, question: str, hits: Sequence[Hit]) -> ModelResponse:
        prompt = build_prompt(question, hits)
        started = time.perf_counter()
        message = await self._client.messages.create(
            model=self.name,
            max_tokens=self._max_tokens,
            system=prompt.system,
            messages=[{"role": "user", "content": prompt.user}],
            # How hard the model thinks and how much it writes. Low is a starting value for
            # reading a few short sections; the evaluation shows whether it is enough.
            output_config={"effort": self._effort},
        )
        seconds = time.perf_counter() - started
        # A reply the safety classifiers stopped has no usable text: it counts as no answer.
        text = ""
        if message.stop_reason != "refusal":
            text = "".join(block.text for block in message.content if block.type == "text")
        return ModelResponse(
            text, self.name, message.usage.input_tokens, message.usage.output_tokens, seconds
        )
