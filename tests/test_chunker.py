from pathlib import Path

import pytest

from labor_rights_rag.chunking.chunker import build_heading, chunk_section, size, split_lines
from labor_rights_rag.parsing.wikitext import Line, Section, parse_law

LAW = "חוק לדוגמה"
FIXTURES = Path(__file__).parent / "fixtures" / "wikisource"
WORDS = "מילה " * 100  # about 500 characters


def sub(text: str) -> Line:
    return Line(2, True, f"(א) {text}")


def para(text: str) -> Line:
    return Line(3, True, f"(1) {text}")


def more(text: str) -> Line:
    return Line(2, False, text)


def _section(lines: list[Line], chapter: str | None = "פרק א") -> Section:
    return Section("7", "כותרת הסעיף", chapter, [5770, 5785], lines)


def test_heading_has_law_chapter_and_section_one_per_line() -> None:
    assert build_heading(LAW, _section([])).splitlines() == [LAW, "פרק א", "7. כותרת הסעיף"]


def test_heading_skips_a_missing_chapter() -> None:
    assert build_heading(LAW, _section([], chapter=None)).splitlines() == [
        LAW,
        "7. כותרת הסעיף",
    ]


def test_short_section_is_one_chunk() -> None:
    section = _section([sub("קצר"), sub("קצר")])

    chunks = chunk_section(LAW, section)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == section.text


def test_text_is_the_body_and_embed_text_adds_the_header() -> None:
    chunk = chunk_section(LAW, _section([sub("קצר")]))[0]

    assert LAW not in chunk.text
    assert chunk.embed_text == f"{chunk.heading_path}\n{chunk.text}"
    assert chunk.heading_path.startswith(LAW)


def test_chunk_keeps_section_number_and_amended_years() -> None:
    chunk = chunk_section(LAW, _section([sub("קצר")]))[0]

    assert chunk.section_number == "7"
    assert chunk.amended_years == [5770, 5785]


def test_long_section_is_cut_between_subsections_and_numbered() -> None:
    section = _section([sub(WORDS), para("פריט"), sub(WORDS), sub(WORDS)])

    chunks = chunk_section(LAW, section, max_chars=1100)

    assert [c.chunk_index for c in chunks] == [0, 1]
    assert all(len(c.text) <= 1100 for c in chunks)
    # The paragraph stays with its subsection: the second chunk starts at a subsection.
    assert chunks[1].text.startswith("(א)")


def test_cut_loses_no_line_and_keeps_the_order() -> None:
    section = _section([sub(WORDS), para(WORDS), more(WORDS), sub(WORDS), sub(WORDS)])

    chunks = chunk_section(LAW, section, max_chars=700)

    assert "\n".join(c.text for c in chunks) == section.text


def test_every_chunk_repeats_the_header() -> None:
    chunks = chunk_section(LAW, _section([sub(WORDS), sub(WORDS), sub(WORDS)]), max_chars=700)

    assert len(chunks) > 1
    assert all(c.embed_text.startswith(c.heading_path) for c in chunks)
    assert all(c.section_number == "7" for c in chunks)


def test_line_without_a_label_never_starts_a_chunk() -> None:
    section = _section([sub(WORDS), more(WORDS), sub(WORDS), more(WORDS)])

    chunks = chunk_section(LAW, section, max_chars=1100)

    assert all(c.text.startswith("(א)") for c in chunks)


def test_subsection_too_long_is_cut_at_paragraphs_with_its_lead_repeated() -> None:
    lead = Line(2, True, "(ג) עובדת רשאית להיעדר מעבודתה:")
    section = _section([lead, para(WORDS), para(WORDS), para(WORDS)])

    chunks = chunk_section(LAW, section, max_chars=1100)

    assert len(chunks) > 1
    assert chunks[0].text.startswith(lead.text)
    # The lead is part of the embedded text of every part, but not of the quote of the others.
    assert all(lead.text in c.embed_text for c in chunks)
    assert all(lead.text not in c.text for c in chunks[1:])
    assert "\n".join(c.text for c in chunks) == section.text


def test_list_of_definitions_is_cut_between_lines() -> None:
    items = [Line(3, True, f"”מונח {i}“ – {WORDS}") for i in range(6)]
    section = _section([Line(1, False, "בחוק זה –"), *items])

    chunks = chunk_section(LAW, section, max_chars=1100)

    assert len(chunks) > 1
    assert all("בחוק זה –" in c.embed_text for c in chunks)


def test_a_single_line_over_the_limit_stays_whole() -> None:
    huge = "(א) " + "מילה " * 600
    chunks = chunk_section(LAW, _section([Line(2, True, huge), sub("קצר")]), max_chars=1500)

    assert chunks[0].text == huge
    assert len(chunks) == 2


@pytest.mark.parametrize("name", ["annual_leave", "advance_notice"])
@pytest.mark.parametrize("max_chars", [200, 400, 1500])
def test_real_laws_are_cut_without_losing_a_line(name: str, max_chars: int) -> None:
    law = parse_law((FIXTURES / f"{name}.wiki").read_text(encoding="utf-8"))

    for section in law.sections:
        chunks = chunk_section(LAW, section, max_chars)
        assert "\n".join(c.text for c in chunks) == section.text
        for part in split_lines(section.lines, max_chars):
            # Only one item may exceed the limit (a line and the lines that continue it):
            # it cannot be cut.
            continued = not any(line.labeled for line in part.lines[1:])
            assert size(part.lines) <= max_chars or continued
