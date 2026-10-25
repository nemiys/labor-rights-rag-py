"""The evaluation questions: a frozen file, read and checked here."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class ExpectedSection(BaseModel):
    law: int  # the Knesset id of the law
    section: str


class Question(BaseModel):
    id: str
    split: Literal["dev", "test"]  # dev: for tuning; test: run once, at the end
    category: str
    question: str
    answerable: bool
    expected: list[ExpectedSection]  # the sections that answer it; empty when not answerable
    # Each group is the ways to say one fact; the fact counts when any of them is in the answer.
    expected_facts: list[list[str]] = []
    notes: str | None = None

    def is_expected(self, law: int, section: str) -> bool:
        return any(e.law == law and e.section == section for e in self.expected)


def load_questions(path: Path) -> list[Question]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Question.model_validate(json.loads(line)) for line in lines if line.strip()]
