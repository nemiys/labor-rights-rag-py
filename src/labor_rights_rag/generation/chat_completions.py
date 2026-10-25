"""The answer written by any model that speaks the `/chat/completions` protocol.

Ollama and most free hosted services accept this request, so one client covers them: only
the address, the model name and the key change. Written with `httpx`, without a framework.
"""

import time
from collections.abc import Sequence

import httpx

from labor_rights_rag.generation.base import ModelResponse
from labor_rights_rag.generation.prompt import build_prompt
from labor_rights_rag.http_retry import with_retries
from labor_rights_rag.retrieval.hit import Hit


class ChatCompletionsAnswerer:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        max_tokens: int = 2000,
        client: httpx.AsyncClient | None = None,
        retry_delays: Sequence[float] = (2.0, 5.0),
    ) -> None:
        self.name = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        # Kept only to send; never printed or put in an error message.
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._max_tokens = max_tokens
        self._client = client or httpx.AsyncClient(timeout=120.0)
        self._retry_delays = retry_delays

    async def answer(self, question: str, hits: Sequence[Hit]) -> ModelResponse:
        prompt = build_prompt(question, hits)
        payload = {
            "model": self.name,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            "temperature": 0,  # the same question should get the same answer
            "max_tokens": self._max_tokens,
        }
        started = time.perf_counter()
        response = await with_retries(
            lambda: self._client.post(self._url, json=payload, headers=self._headers),
            self._retry_delays,
        )
        response.raise_for_status()
        seconds = time.perf_counter() - started

        body = response.json()
        text = body["choices"][0]["message"].get("content") or ""
        usage = body.get("usage") or {}
        return ModelResponse(
            text,
            self.name,
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
            seconds,
        )
