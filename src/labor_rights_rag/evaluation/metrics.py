"""The measures. Pure functions, so they can be tested without a database or a model."""

from collections.abc import Sequence
from dataclasses import dataclass

from labor_rights_rag.evaluation.questions import Question
from labor_rights_rag.retrieval.hit import Hit
from labor_rights_rag.retrieval.normalize import tokens


def first_relevant_rank(hits: Sequence[Hit], question: Question) -> int | None:
    """The rank of the first chunk that belongs to an expected section, or None."""
    for hit in hits:
        if question.is_expected(hit.law_odata_id, hit.section_number):
            return hit.rank
    return None


def hit_at(rank: int | None, k: int) -> bool:
    return rank is not None and rank <= k


def reciprocal_rank(rank: int | None, depth: int) -> float:
    """1 / rank, and 0 when the first relevant chunk is not within the depth."""
    return 1 / rank if rank is not None and rank <= depth else 0.0


def recall_at(hits: Sequence[Hit], question: Question, k: int) -> float:
    """The share of the expected sections that are among the first k chunks."""
    if not question.expected:
        return 0.0
    top = {(h.law_odata_id, h.section_number) for h in hits[:k]}
    found = sum((e.law, e.section) in top for e in question.expected)
    return found / len(question.expected)


def _words(text: str) -> str:
    return " ".join(tokens(text))


def facts_found(answer: str, groups: Sequence[Sequence[str]]) -> bool:
    """Every group must have at least one of its phrasings in the answer. No groups: True."""
    text = _words(answer)
    return all(any(_words(variant) in text for variant in group) for group in groups)


@dataclass(frozen=True)
class ThresholdRow:
    threshold: float
    false_refusals: float  # share of answerable questions that would be refused
    answered_without_source: float  # share of unanswerable questions that pass the threshold


def threshold_sweep(
    answerable: Sequence[float], unanswerable: Sequence[float], thresholds: Sequence[float]
) -> list[ThresholdRow]:
    """For each threshold, what a refusal below it would do to both kinds of question."""
    return [
        ThresholdRow(
            t,
            sum(score < t for score in answerable) / len(answerable) if answerable else 0.0,
            sum(score >= t for score in unanswerable) / len(unanswerable) if unanswerable else 0.0,
        )
        for t in thresholds
    ]
