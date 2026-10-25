"""Chooses the model that writes the answers by name."""

from labor_rights_rag.generation.base import Answerer
from labor_rights_rag.generation.chat_completions import ChatCompletionsAnswerer
from labor_rights_rag.generation.claude import ClaudeAnswerer
from labor_rights_rag.generation.fake import FakeAnswerer
from labor_rights_rag.settings import settings

ANSWERER_NAMES = ("fake", "claude", "chat")


def make_answerer(name: str) -> Answerer:
    if name == "fake":
        return FakeAnswerer()
    if name == "claude":
        if settings.anthropic_api_key is None:
            raise ValueError("ANSWERER=claude needs ANTHROPIC_API_KEY (in .env, never in code)")
        return ClaudeAnswerer(
            settings.anthropic_api_key.get_secret_value(),
            settings.answer_model,
            settings.answer_effort,
        )
    if name == "chat":
        if not settings.chat_model:
            raise ValueError("ANSWERER=chat needs CHAT_MODEL (and CHAT_BASE_URL, CHAT_API_KEY)")
        key = settings.chat_api_key.get_secret_value() if settings.chat_api_key else None
        return ChatCompletionsAnswerer(settings.chat_base_url, key, settings.chat_model)
    raise ValueError(f"unknown answerer: {name}")
