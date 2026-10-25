"""Reads what the model wrote: is it a refusal, and which sources does it cite."""

import re
from dataclasses import dataclass

from labor_rights_rag.generation.prompt import NO_ANSWER_MARKER

# [1], [2][3] and [1, 2]
_CITATION = re.compile(r"\[(\d+(?:\s*[,،]\s*\d+)*)\]")


@dataclass(frozen=True)
class ParsedAnswer:
    refused: bool
    text: str  # as the model wrote it
    citations: list[int]  # the valid source numbers, each once, in order of appearance
    invalid_citations: list[int]  # numbers outside 1..source_count: the model made them up


def parse_answer(text: str, source_count: int) -> ParsedAnswer:
    stripped = text.strip()
    refused = not stripped or stripped.startswith(NO_ANSWER_MARKER)

    citations: list[int] = []
    invalid: list[int] = []
    for group in _CITATION.findall(stripped):
        for number in (int(part) for part in re.split(r"[,،]", group)):
            valid = 1 <= number <= source_count
            seen = citations if valid else invalid
            if number not in seen:
                seen.append(number)
    return ParsedAnswer(refused, stripped, citations, invalid)
