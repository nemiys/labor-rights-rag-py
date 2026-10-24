"""Checks the real model. Skipped unless RUN_MODEL_TESTS=1, since it loads about 2 GB."""

import os

import pytest

from labor_rights_rag.embeddings.base import EMBEDDING_DIM

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MODEL_TESTS") != "1", reason="loads the real model; set RUN_MODEL_TESTS=1"
)


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_real_model_puts_a_paraphrase_closer_than_an_unrelated_text() -> None:
    from labor_rights_rag.embeddings.bge_m3 import BgeM3Embedder

    embedder = BgeM3Embedder()
    question = embedder.embed_query("כמה ימי חופש מגיעים לי בשנה?")
    related, unrelated = embedder.embed_documents(
        [
            "עובד זכאי לחופשה שנתית בשנה הראשונה לעבודתו, ומספר הימים נקבע לפי ותק",
            "המעסיק ישלם שכר בעד שעות נוספות בתוספת של עשרים וחמישה אחוזים",
        ]
    )

    assert len(question) == EMBEDDING_DIM
    assert abs(cosine(question, question) - 1.0) < 1e-4
    assert cosine(question, related) > cosine(question, unrelated)
