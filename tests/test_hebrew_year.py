import pytest

from labor_rights_rag.parsing.hebrew_year import parse_amendment_years, parse_hebrew_year


@pytest.mark.parametrize(
    ("text", "year"),
    [
        ("תשע״ד", 5774),
        ("תש״ן", 5750),  # final nun
        ("תש״ך", 5720),  # final kaf
        ("תשפ״ו", 5786),
        ("תשע״ד־2", 5774),  # second amendment in the same year
        ('תשע"ד', 5774),  # plain double quote instead of gershayim
    ],
)
def test_parses_hebrew_years(text: str, year: int) -> None:
    assert parse_hebrew_year(text) == year


@pytest.mark.parametrize("text", ["ק״ת", "603", "[י״פ הודעות]", "", "תיקון"])
def test_rejects_things_that_are_not_years(text: str) -> None:
    assert parse_hebrew_year(text) is None


def test_amendment_tag_gives_sorted_unique_years() -> None:
    tag = "תיקון: תשע״ו, תשכ״ה, תשכ״ז, תשע״ד־2, תשע״ד"

    assert parse_amendment_years(tag) == [5725, 5727, 5774, 5776]


def test_amendment_tag_skips_parts_that_are_not_years() -> None:
    assert parse_amendment_years("תיקון: ק״ת תשל״ג, [י״פ הודעות], תשמ״ה") == [5745]
