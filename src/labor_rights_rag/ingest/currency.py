"""Is the text we have as recent as the Knesset says the law is? (ADR-0003)

The Open Law Book tells us the Hebrew year of the latest amendment it merged; the
Knesset registry tells us the date of the latest publication. We compare years.
"""

from datetime import date

OK, AHEAD, BEHIND, UNKNOWN = "ok", "ahead", "behind", "unknown"


def hebrew_years_of(day: date) -> set[int]:
    """The Hebrew year(s) a Gregorian date may fall in.

    A Hebrew year starts at Rosh Hashanah, which moves between September 5 and
    October 5. Inside that window we cannot tell without a calendar, so both years
    are possible; outside it the answer is exact.
    """
    before = day.year + 3760  # January to the start of September
    after = day.year + 3761  # after Rosh Hashanah
    if day.month < 9:
        return {before}
    if day.month == 9 or (day.month == 10 and day.day <= 5):
        return {before, after}
    return {after}


def currency_status(text_year: int | None, knesset_date: date | None) -> str:
    if text_year is None or knesset_date is None:
        return UNKNOWN
    years = hebrew_years_of(knesset_date)
    if text_year in years:
        return OK
    # The text mentions a later amendment than the registry: the registry field may lag.
    if text_year > max(years):
        return AHEAD
    # The Knesset published something the text does not include yet: a warning.
    return BEHIND
