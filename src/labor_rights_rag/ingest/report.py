"""A Markdown report of an ingest run: what was found, what was stored, what to check."""

from labor_rights_rag.ingest.pipeline import LawResult
from labor_rights_rag.parsing.hebrew_year import format_hebrew_year


def format_report(results: list[LawResult]) -> str:
    stored = sum(r.storable for r in results)
    lines = [
        "# Ingest report",
        "",
        f"Laws in corpus: {len(results)}. Stored: {stored}. Not stored: {len(results) - stored}.",
        "",
        "| Law | Knesset id | Last amendment (text) | Last publication (Knesset) "
        "| Status | Sections | Longest section | Change | Notes |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        sections = r.parsed.sections if r.parsed else []
        year = r.parsed.last_amendment_year if r.parsed else None
        notes = "; ".join(r.issues + r.warnings)
        lines.append(
            "| "
            + " | ".join(
                [
                    r.corpus.title,
                    str(r.knesset.odata_id) if r.knesset else "-",
                    format_hebrew_year(year) if year else "-",
                    str(r.knesset.latest_publication_date or "-") if r.knesset else "-",
                    r.status,
                    str(len(sections)),
                    str(max((len(s.text) for s in sections), default=0)),
                    r.change or "-",
                    notes or "-",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"
