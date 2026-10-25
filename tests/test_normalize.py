from labor_rights_rag.retrieval.normalize import query_terms, stems, to_search_text, tokens


def test_niqqud_is_removed() -> None:
    assert tokens("חֻפְשָׁה") == ["חפשה"]


def test_gershayim_do_not_split_a_word() -> None:
    assert tokens('התשי״א התשי"א') == ["התשיא", "התשיא"]


def test_hyphens_and_punctuation_separate_words() -> None:
    assert tokens("תל־אביב, חיפה; (ב)") == ["תל", "אביב", "חיפה", "ב"]


def test_maqaf_separates_words_and_is_not_dropped_like_a_point() -> None:
    assert tokens("מ־5 השנים ארץ־ישראל") == ["מ", "5", "השנים", "ארץ", "ישראל"]


def test_section_number_with_a_letter_is_one_word() -> None:
    assert tokens("סעיף 14א") == ["סעיף", "14א"]


def test_latin_is_lowercased() -> None:
    assert tokens("BGE-M3") == ["bge", "m3"]


def test_one_and_two_prefix_letters_are_stripped() -> None:
    assert stems("בחופשה") == ["חופשה"]
    assert stems("והחופשה") == ["החופשה", "חופשה"]


def test_a_word_is_never_stripped_below_three_letters() -> None:
    assert stems("שכר") == []  # "כר" would be two letters
    assert stems("בית") == []


def test_numbers_and_latin_have_no_prefix_forms() -> None:
    assert stems("14א") == []
    assert stems("bge") == []


def test_search_text_keeps_the_original_word_and_adds_the_stem() -> None:
    assert to_search_text("עובד בחופשה") == "עובד בחופשה חופשה"


def test_question_words_are_dropped_from_the_query() -> None:
    assert query_terms("כמה ימי חופש צריך לי?") == ["ימי", "חופש", "צריך"]


def test_framing_words_of_the_domain_are_dropped_but_the_number_stays() -> None:
    assert query_terms("סעיף 14א בחוק") == ["14א", "בחוק"]


def test_query_terms_are_distinct_and_include_prefix_less_forms() -> None:
    assert query_terms("בחופשה חופשה") == ["בחופשה", "חופשה"]


def test_a_question_of_only_question_words_has_no_terms() -> None:
    assert query_terms("מה כמה לי?") == []


def test_query_terms_hold_only_letters_and_digits() -> None:
    # What goes into a tsquery must not carry operators, quotes or SQL.
    terms = query_terms("'); DROP TABLE chunks; -- | & ! ( ) :*")

    assert terms == ["drop", "table", "chunks"]
