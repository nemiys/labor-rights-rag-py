import json
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
import respx
from anthropic import AsyncAnthropic
from pydantic import SecretStr

from labor_rights_rag.generation.chat_completions import ChatCompletionsAnswerer
from labor_rights_rag.generation.claude import ClaudeAnswerer
from labor_rights_rag.generation.factory import make_answerer
from labor_rights_rag.generation.fake import FakeAnswerer
from labor_rights_rag.generation.parse import parse_answer
from labor_rights_rag.generation.pricing import estimate_cost_usd
from labor_rights_rag.retrieval.hit import Hit
from labor_rights_rag.settings import settings

HITS = [Hit(1, 0.7, 1, 1, "חוק חופשה", "3", 0, "עובד זכאי לחופשה")]
BASE = "https://llm.example/v1beta/openai/"
URL = "https://llm.example/v1beta/openai/chat/completions"


# Claude, through the SDK (a stand-in client: no network, no key)


class FakeMessages:
    def __init__(self, message: Any) -> None:
        self.message = message
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.message


def _claude(message: Any) -> tuple[ClaudeAnswerer, FakeMessages]:
    messages = FakeMessages(message)
    client = cast(AsyncAnthropic, SimpleNamespace(messages=messages))
    return ClaudeAnswerer("unused", "claude-sonnet-5-5", effort="low", client=client), messages


def _message(blocks: list[Any], stop_reason: str = "end_turn") -> Any:
    usage = SimpleNamespace(input_tokens=1200, output_tokens=300)
    return SimpleNamespace(content=blocks, usage=usage, stop_reason=stop_reason)


async def test_claude_gets_the_prompt_the_model_and_the_effort() -> None:
    answerer, messages = _claude(_message([SimpleNamespace(type="text", text="תשובה [1]")]))

    await answerer.answer("כמה ימי חופש", HITS)

    call = messages.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["output_config"] == {"effort": "low"}
    assert call["max_tokens"] == 4000
    assert "only the numbered sources" in call["system"]
    assert '<source id="1"' in call["messages"][0]["content"]
    assert "temperature" not in call  # sampling parameters are not sent


async def test_claude_text_is_the_text_blocks_only_and_usage_is_recorded() -> None:
    blocks = [
        SimpleNamespace(type="thinking", thinking="חשבתי"),
        SimpleNamespace(type="text", text="מגיעים ימים [1]."),
    ]
    answerer, _ = _claude(_message(blocks))

    response = await answerer.answer("שאלה", HITS)

    assert response.text == "מגיעים ימים [1]."
    assert (response.model, response.input_tokens, response.output_tokens) == (
        "claude-sonnet-5-5",
        1200,
        300,
    )
    assert response.seconds >= 0


async def test_a_reply_stopped_by_the_safety_classifiers_counts_as_no_answer() -> None:
    blocks = [SimpleNamespace(type="text", text="חצי תשובה")]
    answerer, _ = _claude(_message(blocks, stop_reason="refusal"))

    response = await answerer.answer("שאלה", HITS)

    assert parse_answer(response.text, 1).refused


# Any model that speaks /chat/completions (respx plays the server)


def _completion(text: str = "תשובה [1]") -> dict[str, Any]:
    return {
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 800, "completion_tokens": 120},
    }


@respx.mock
async def test_chat_request_has_the_address_the_key_and_the_two_messages() -> None:
    route = respx.post(URL).respond(json=_completion())
    answerer = ChatCompletionsAnswerer(BASE, "secret-key", "some-model")

    response = await answerer.answer("כמה ימי חופש", HITS)

    request = route.calls.last.request
    sent = json.loads(request.content)
    assert request.headers["authorization"] == "Bearer secret-key"
    assert sent["model"] == "some-model"
    assert [m["role"] for m in sent["messages"]] == ["system", "user"]
    assert sent["temperature"] == 0
    assert (response.text, response.input_tokens, response.output_tokens) == ("תשובה [1]", 800, 120)


@respx.mock
async def test_chat_without_a_key_sends_no_authorization_header() -> None:
    route = respx.post(URL).respond(json=_completion())

    await ChatCompletionsAnswerer(BASE, None, "local-model").answer("שאלה", HITS)

    assert "authorization" not in route.calls.last.request.headers


@respx.mock
async def test_chat_missing_content_and_usage_do_not_break_it() -> None:
    respx.post(URL).respond(json={"choices": [{"message": {"content": None}}]})

    response = await ChatCompletionsAnswerer(BASE, None, "m").answer("שאלה", HITS)

    assert parse_answer(response.text, 1).refused
    assert (response.input_tokens, response.output_tokens) == (0, 0)


@respx.mock
async def test_chat_retries_a_busy_server_and_then_succeeds() -> None:
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(429),
            httpx.ReadError("dropped"),
            httpx.Response(200, json=_completion()),
        ]
    )
    answerer = ChatCompletionsAnswerer(BASE, "k", "m", retry_delays=(0, 0))

    response = await answerer.answer("שאלה", HITS)

    assert response.text == "תשובה [1]"
    assert route.call_count == 3


@respx.mock
async def test_chat_error_does_not_contain_the_key() -> None:
    respx.post(URL).respond(401, json={"error": "bad key"})
    answerer = ChatCompletionsAnswerer(BASE, "secret-key", "m", retry_delays=(0,))

    with pytest.raises(httpx.HTTPStatusError) as error:
        await answerer.answer("שאלה", HITS)

    assert "secret-key" not in str(error.value)


# Choosing by name


def test_unknown_answerer_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown answerer"):
        make_answerer("gpt")


def test_the_fake_needs_no_setting() -> None:
    assert isinstance(make_answerer("fake"), FakeAnswerer)


def test_claude_without_a_key_says_what_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", None)

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        make_answerer("claude")


def test_claude_with_a_key_is_built_without_calling_anything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", SecretStr("sk-test"))

    assert make_answerer("claude").name == settings.answer_model


def test_chat_without_a_model_says_what_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "chat_model", "")

    with pytest.raises(ValueError, match="CHAT_MODEL"):
        make_answerer("chat")


def test_the_key_is_never_shown_when_settings_are_printed() -> None:
    assert "sk-test" not in repr(SecretStr("sk-test"))


# Cost


def test_cost_follows_the_price_list() -> None:
    # 1,200 tokens in at 2 dollars and 300 out at 10 dollars, per million.
    assert estimate_cost_usd("claude-sonnet-5-5", 1200, 300) == pytest.approx(0.0054)


def test_a_model_that_is_not_in_the_price_list_has_no_cost() -> None:
    assert estimate_cost_usd("some-free-model", 1200, 300) is None
    assert estimate_cost_usd(None, 0, 0) is None
