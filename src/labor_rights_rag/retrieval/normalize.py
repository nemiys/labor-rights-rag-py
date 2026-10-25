"""Hebrew text for full-text search. See docs/adr/0006-hebrew-text-search.md.

Postgres has no Hebrew dictionary, so the text is cleaned here: niqqud and quotation
marks go, and every word is also indexed without its prefix letters ("בחופשה" also gives
"חופשה"). The same cleaning is applied to the question, so both sides meet.
"""

import re

_NIQQUD = re.compile(r"[֑-ׇ]")  # points and cantillation marks
# Punctuation that sits inside that range but separates words: maqaf (תל־אביב), paseq,
# sof pasuq, nun hafukha. They must become spaces before the range is removed.
_SEPARATORS = str.maketrans("־׀׃׆", "    ")
# Gershayim and geresh (התשי״א), straight and curly quotes, apostrophes: removed, so that
# "התשי״א" stays one word instead of splitting in two.
_QUOTES = str.maketrans("", "", "״׳\"'“”‘’„‟`")
_WORD = re.compile(r"[^\W_]+")  # letters and digits; "14א" is one word

_PREFIX_LETTERS = "הובכלמש"
_MAX_PREFIXES = 2
_MIN_STEM = 3  # never strip a word down to fewer letters

# Question and function words, dropped from the question only (the text keeps them). Also
# "סעיף", "סעיפים" and "חוק": in this corpus they are in almost every chunk (the law name in
# the header, section references in the body), so they say nothing about which one is meant,
# and full-text ranking would let them outweigh a rare word such as "14א".
STOPWORDS = frozenset(
    """
    של את על לי לו לה לנו לך מה כמה מי איך למה מתי איפה אם או גם כל זה זו זאת הוא היא הם הן
    אני אתה אנחנו יש אין לא כן אבל כי עם אל מן בין עד אחרי לפני האם אותי אותו אותה
    סעיף סעיפים חוק
    """.split()
)


def _is_hebrew(word: str) -> bool:
    return "א" <= word[0] <= "ת"


def tokens(text: str) -> list[str]:
    """The words of a text, cleaned. No prefix handling yet."""
    cleaned = _NIQQUD.sub("", text.translate(_SEPARATORS)).translate(_QUOTES).lower()
    return _WORD.findall(cleaned)


def stems(word: str) -> list[str]:
    """The word without one prefix letter, and without two ("והחופשה": "החופשה", "חופשה")."""
    forms: list[str] = []
    current = word
    if not _is_hebrew(word):
        return forms
    for _ in range(_MAX_PREFIXES):
        if current[0] in _PREFIX_LETTERS and len(current) - 1 >= _MIN_STEM:
            current = current[1:]
            forms.append(current)
        else:
            break
    return forms


def to_search_text(text: str) -> str:
    """What is stored in `chunks.search_text`: every word and its prefix-less forms."""
    words: list[str] = []
    for word in tokens(text):
        words.append(word)
        words.extend(stems(word))
    return " ".join(words)


def query_terms(question: str) -> list[str]:
    """The distinct words to search for: question words dropped, prefix-less forms added."""
    terms: list[str] = []
    for word in tokens(question):
        for form in [word, *stems(word)]:
            if form not in STOPWORDS and form not in terms:
                terms.append(form)
    return terms
