"""Hebrew years written in letters ("תשע״ד") to numbers (5774)."""

import re

_VALUES = {
    "א": 1, "ב": 2, "ג": 3, "ד": 4, "ה": 5, "ו": 6, "ז": 7, "ח": 8, "ט": 9,
    "י": 10, "כ": 20, "ך": 20, "ל": 30, "מ": 40, "ם": 40, "נ": 50, "ן": 50,
    "ס": 60, "ע": 70, "פ": 80, "ף": 80, "צ": 90, "ץ": 90,
    "ק": 100, "ר": 200, "ש": 300, "ת": 400,
}  # fmt: skip

# A year is a run of Hebrew letters with a gershayim (״ or ") before the last one,
# optionally followed by "־2", "-3"... when the same year had several amendments.
_YEAR = re.compile(r"^\s*([א-ת]+)[״\"]([א-ת])(?:\s*[־-]\s*\d+)?\s*$")


def parse_hebrew_year(text: str) -> int | None:
    """Return the full year (5774), or None for anything that is not a year (e.g. "ק״ת").

    Years are written without the thousands, so "תשע״ד" is 774 + 5000. Only the
    modern range is accepted, which also filters out abbreviations like "ק״ת" (=500).
    """
    match = _YEAR.match(text)
    if not match:
        return None
    value = sum(_VALUES[letter] for letter in match.group(1) + match.group(2))
    return 5000 + value if 700 <= value <= 999 else None


def format_hebrew_year(year: int) -> str:
    """5786 -> '5786 (2025-26)': the Hebrew year spans two Gregorian years."""
    return f"{year} ({year - 3761}-{str(year - 3760)[-2:]})"


def parse_amendment_years(tag: str) -> list[int]:
    """'תיקון: תשכ״ה, תשע״ד־2' -> [5725, 5774]. Unknown parts are skipped."""
    body = tag.split(":", 1)[1] if ":" in tag else tag
    years = {year for part in body.split(",") if (year := parse_hebrew_year(part))}
    return sorted(years)
