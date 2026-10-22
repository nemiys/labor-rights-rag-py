from datetime import date

import pytest

from labor_rights_rag.ingest.currency import (
    AHEAD,
    BEHIND,
    OK,
    UNKNOWN,
    currency_status,
    hebrew_years_of,
)


@pytest.mark.parametrize(
    ("day", "years"),
    [
        (date(2026, 7, 20), {5786}),  # summer: still the year that began last autumn
        (date(2017, 11, 7), {5778}),  # after Rosh Hashanah
        (date(2025, 9, 20), {5785, 5786}),  # Rosh Hashanah window: either year
    ],
)
def test_hebrew_years_of_a_date(day: date, years: set[int]) -> None:
    assert hebrew_years_of(day) == years


@pytest.mark.parametrize(
    ("text_year", "knesset_date", "status"),
    [
        (5786, date(2026, 7, 20), OK),  # annual leave law, October 2026
        (5786, date(2025, 1, 30), AHEAD),  # severance pay: the registry field lags
        (5778, date(2023, 6, 6), BEHIND),  # the text misses a newer amendment
        (5786, date(2025, 9, 20), OK),  # inside the window, either year counts
        (None, date(2026, 7, 20), UNKNOWN),
        (5786, None, UNKNOWN),
    ],
)
def test_currency_status(text_year: int | None, knesset_date: date | None, status: str) -> None:
    assert currency_status(text_year, knesset_date) == status
