from pathlib import Path

import pytest

from labor_rights_rag.parsing.wikitext import ParsedLaw, parse_law, render

FIXTURES = Path(__file__).parent / "fixtures" / "wikisource"


@pytest.fixture(scope="module")
def annual_leave() -> ParsedLaw:
    return parse_law((FIXTURES / "annual_leave.wiki").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def advance_notice() -> ParsedLaw:
    return parse_law((FIXTURES / "advance_notice.wiki").read_text(encoding="utf-8"))


def test_link_keeps_its_display_text() -> None:
    text = "לפי {{ח:חיצוני|חוק שירות המילואים|חוק שירות המילואים, התשס״ח–2008}};"

    assert render(text) == "לפי חוק שירות המילואים, התשס״ח–2008;"


def test_link_without_display_text_uses_the_target_without_anchor() -> None:
    assert render("{{ח:פנימי|סעיף 18#א}}") == "סעיף 18"


def test_editor_note_is_dropped_even_with_a_nested_link() -> None:
    text = "טקסט {{ח:הערה|פורסמו {{ח:חיצוני|תקנות א|תקנות א, תשכ״ד}}.}}"

    assert render(text) == "טקסט"


def test_section_without_body_is_dropped() -> None:
    law = parse_law("{{ח:סעיף|1|ריק}}\n{{ח:סעיף|2|מלא}}\n{{ח:ת}} יש כאן טקסט.")

    assert [s.number for s in law.sections] == ["2"]


def test_signatures_end_the_last_section() -> None:
    law = parse_law("{{ח:סעיף|1|א}}\n{{ח:ת}} טקסט.\n{{ח:חתימות|נתקבל}}\n* דוד בן גוריון")

    assert law.sections[0].text == "טקסט."


def test_reads_the_knesset_registry_id(annual_leave: ParsedLaw) -> None:
    assert annual_leave.knesset_id == 2000658


def test_section_has_title_chapter_amendments_and_text(annual_leave: ParsedLaw) -> None:
    section = next(s for s in annual_leave.sections if s.number == "3")

    assert section.title == "אורך החופשה"
    assert section.chapter == "פרק שני: החופשה"
    assert section.amended_years == [5725, 5727, 5774, 5776]
    assert "(1) בעד כל אחת מ־5 השנים הראשונות – 16 יום;" in section.text


def test_item_left_with_only_a_label_is_dropped(annual_leave: ParsedLaw) -> None:
    section = next(s for s in annual_leave.sections if s.number == "3")

    assert "(2)" not in [line.text for line in section.lines]


def test_each_line_keeps_the_level_the_page_gives_it() -> None:
    law = parse_law(
        "{{ח:סעיף|2|כותרת}}\n"
        "{{ח:תת|(א)}} סעיף קטן –\n"
        "{{ח:תתת|(1)}} פסקה;\n"
        "{{ח:תתתת|(ב)}} פסקת משנה."
    )

    assert [(line.level, line.labeled) for line in law.sections[0].lines] == [
        (2, True),
        (3, True),
        (4, True),
    ]


def test_line_without_a_label_continues_the_one_before() -> None:
    law = parse_law("{{ח:סעיף|2|כותרת}}\n{{ח:תת|(א)}} סעיף קטן.\n{{ח:תת}} אולם המשך.")

    assert [line.labeled for line in law.sections[0].lines] == [True, False]


def test_definition_is_its_own_item_though_it_has_no_label() -> None:
    law = parse_law("{{ח:סעיף|1|הגדרות}}\n{{ח:תתת|סוג=הגדרה}} ”מונח“ – פירוש;")

    assert law.sections[0].lines[0].labeled


def test_no_markup_is_left_in_any_section(annual_leave: ParsedLaw) -> None:
    for section in annual_leave.sections:
        assert not any(mark in section.text for mark in ("{{", "}}", "[[", "]]", "<"))


def test_schedule_items_are_numbered_by_their_anchor(annual_leave: ParsedLaw) -> None:
    numbers = [s.number for s in annual_leave.sections]

    assert "תוספת פרט 9" in numbers


def test_last_amendment_comes_with_its_official_pdf(annual_leave: ParsedLaw) -> None:
    last = annual_leave.amendments[-1]

    assert annual_leave.last_amendment_year == 5786
    assert last.label == "תיקון מס׳ 17"
    assert last.url.startswith("https://fs.knesset.gov.il/") and last.url.endswith(".pdf")


def test_amendment_without_a_year_inherits_the_previous_one(annual_leave: ParsedLaw) -> None:
    # In the source, "603" follows "תשע״ד, 575" and has no year of its own.
    replacement = next(a for a in annual_leave.amendments if "החלפת המונח" in a.label)

    assert replacement.year == 5774


def test_a_second_law_parses_with_the_same_rules(advance_notice: ParsedLaw) -> None:
    assert advance_notice.knesset_id == 2000283
    assert len(advance_notice.sections) == 14
    assert advance_notice.last_amendment_year == 5774
