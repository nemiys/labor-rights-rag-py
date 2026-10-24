from labor_rights_rag.embeddings.fake import HashEmbedder


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_vector_has_the_requested_dimension() -> None:
    assert len(HashEmbedder(dim=64).embed_query("חופשה שנתית")) == 64


def test_same_text_gives_the_same_vector() -> None:
    embedder = HashEmbedder()

    assert embedder.embed_query("חופשה שנתית") == embedder.embed_query("חופשה שנתית")


def test_vector_has_unit_length() -> None:
    vector = HashEmbedder().embed_query("עובד זכאי לחופשה שנתית")

    assert abs(cosine(vector, vector) - 1.0) < 1e-9


def test_texts_sharing_words_are_closer_than_texts_sharing_none() -> None:
    embedder = HashEmbedder()
    query = embedder.embed_query("ימי חופשה שנתית")
    related, unrelated = embedder.embed_documents(
        ["עובד זכאי לחופשה שנתית בת ימים", "שעות נוספות משולמות בתוספת"]
    )

    assert cosine(query, related) > cosine(query, unrelated)


def test_empty_text_gives_a_zero_vector_and_no_error() -> None:
    assert set(HashEmbedder(dim=8).embed_query("")) == {0.0}
