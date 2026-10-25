"""Chooses the model that writes the answers by name."""

from labor_rights_rag.generation.base import Answerer
from labor_rights_rag.generation.fake import FakeAnswerer

ANSWERER_NAMES = ("fake",)


def make_answerer(name: str) -> Answerer:
    if name == "fake":
        return FakeAnswerer()
    raise ValueError(f"unknown answerer: {name}")
