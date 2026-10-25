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
        # Kept only to send; never printed. It is removed from error messages below.
        self._key = api_key
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
        seconds = time.perf_counter() - started
        if response.is_error:
            # Say why the server refused: "403" alone does not tell a wrong key from a busy model.
            detail = response.text.replace(self._key, "***") if self._key else response.text
            raise httpx.HTTPStatusError(
                f"{response.status_code} from {self._url}: {detail[:300]}",
                request=response.request,
                response=response,
            )

        body = response.json()
        text = body["choices"][0]["message"].get("content") or ""
        usage = body.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        # Some services keep the model's hidden thinking out of completion_tokens but count it
        # in total_tokens, and bill it. The larger of the two is the honest output size.
        output_tokens = max(
            int(usage.get("completion_tokens", 0)),
            int(usage.get("total_tokens", 0)) - prompt_tokens,
        )
        return ModelResponse(text, self.name, prompt_tokens, output_tokens, seconds)
