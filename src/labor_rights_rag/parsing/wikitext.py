"""Turns the wikitext of an Open Law Book page into sections.

The pages use a fixed set of templates (all named "ח:..."):
  {{ח:קטע2|anchor|title}}               chapter heading
  {{ח:סעיף|3|title|תיקון: תשכ״ה, ...}}   start of a section, with its amendment years
  {{ח:ת}} / {{ח:תת|(א)}} / {{ח:תתת|(1)}}  a line of the section body, with its label
  {{ח:חיצוני|target|text}}, {{ח:פנימי|target|text}}   links: keep the text
  {{ח:הערה|...}}                         an editor's note, not the law's words: dropped
  {{ח:מאגר|2000658}}                     the law's id in the Knesset registry
  {{ח:תיבה|תשע״ד, 575|label|url}}        one amendment as published in Reshumot
"""

import re
from dataclasses import dataclass, field

from labor_rights_rag.parsing.hebrew_year import parse_amendment_years, parse_hebrew_year


@dataclass(frozen=True)
class Amendment:
    year: int | None  # Hebrew year, e.g. 5786; None when the source does not say
    label: str
    url: str  # the amendment as published in Reshumot (official PDF)


@dataclass(frozen=True)
class Line:
    """One line of a section body, with the structure the page gives it."""

    level: int  # 2 = subsection "(א)", 3 = paragraph "(1)", 4 = sub-paragraph; 0 = plain text
    labeled: bool  # False for a line that continues the one before it
    text: str


@dataclass
class Section:
    number: str
    title: str
    chapter: str | None
    amended_years: list[int]
    lines: list[Line] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


@dataclass
class ParsedLaw:
    knesset_id: int | None
    sections: list[Section]
    amendments: list[Amendment]

    @property
    def last_amendment_year(self) -> int | None:
        years = [a.year for a in self.amendments if a.year]
        years += [y for s in self.sections for y in s.amended_years]
        return max(years, default=None)


@dataclass(frozen=True)
class _Template:
    name: str
    args: list[str]  # positional arguments, raw (may contain nested templates)
    named: dict[str, str]


def _split_top_level(text: str) -> list[str]:
    """Split on "|" that is not inside a nested {{template}} or [[link]]."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    i = 0
    while i < len(text):
        pair = text[i : i + 2]
        if pair in ("{{", "[["):
            depth += 1
            current.append(pair)
            i += 2
        elif pair in ("}}", "]]") and depth:
            depth -= 1
            current.append(pair)
            i += 2
        elif text[i] == "|" and depth == 0:
            parts.append("".join(current))
            current = []
            i += 1
        else:
            current.append(text[i])
            i += 1
    parts.append("".join(current))
    return parts


def _parse_template(inner: str) -> _Template:
    name, *rest = _split_top_level(inner)
    args: list[str] = []
    named: dict[str, str] = {}
    for part in rest:
        key, eq, value = part.partition("=")
        if eq and "{{" not in key and key.strip():
            named[key.strip()] = value.strip()
        else:
            args.append(part.strip())
    return _Template(name.strip(), args, named)


def _find_templates(text: str) -> list[tuple[int, int, _Template]]:
    """Top-level templates in text, as (start, end, template). Nested ones stay in args."""
    found: list[tuple[int, int, _Template]] = []
    depth = 0
    start = 0
    i = 0
    while i < len(text) - 1:
        if text[i : i + 2] == "{{":
            if depth == 0:
                start = i
            depth += 1
            i += 2
        elif text[i : i + 2] == "}}" and depth:
            depth -= 1
            i += 2
            if depth == 0:
                found.append((start, i, _parse_template(text[start + 2 : i - 2])))
        else:
            i += 1
    return found


def _arg(template: _Template, index: int) -> str:
    return template.args[index] if len(template.args) > index else ""


_LINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]")
_TAG = re.compile(r"<[^>]+>")


def render(text: str) -> str:
    """Plain text of a wikitext fragment: links keep their text, notes and markup go away."""
    out: list[str] = []
    last = 0
    for start, end, template in _find_templates(text):
        out.append(text[last:start])
        if template.name in ("ח:חיצוני", "ח:פנימי"):
            out.append(render(_arg(template, 1) or _arg(template, 0).split("#")[0]))
        last = end
    out.append(text[last:])
    plain = _TAG.sub("", _LINK.sub(r"\1", "".join(out)))
    return re.sub(r"[ \t]+", " ", plain).strip()


_BODY_LINE = re.compile(r"^\{\{ח:ת+[|}]")


def parse_law(wikitext: str) -> ParsedLaw:
    knesset_id: int | None = None
    amendments: list[Amendment] = []
    sections: list[Section] = []
    chapter: str | None = None
    current: Section | None = None
    last_year: int | None = None

    for raw_line in wikitext.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        templates = _find_templates(line)
        first = templates[0][2] if templates and templates[0][0] == 0 else None

        for _, _, template in templates:
            if template.name == "ח:מאגר" and _arg(template, 0).isdigit():
                knesset_id = int(_arg(template, 0))
            elif template.name == "ח:תיבה":
                # "תשע״ד, 575" carries a year; a bare "603" continues the previous one.
                year = parse_hebrew_year(_arg(template, 0).split(",")[0]) or last_year
                last_year = year
                amendments.append(Amendment(year, render(_arg(template, 1)), _arg(template, 2)))

        if first is None:
            if current is not None and (text := render(line)):
                current.lines.append(Line(0, False, text))
            continue

        if first.name.startswith("ח:קטע"):
            chapter = render(_arg(first, 1) or _arg(first, 0))
            current = None
        elif first.name in ("ח:סעיף", "ח:סעיף*"):
            title = _arg(first, 1)
            tags = [a for a in first.args if a.startswith("תיקון")]
            current = Section(
                number=render(first.named.get("עוגן") or _arg(first, 0)),
                title="" if title.startswith("תיקון") else render(title),
                chapter=chapter,
                amended_years=sorted({y for tag in tags for y in parse_amendment_years(tag)}),
            )
            sections.append(current)
        elif _BODY_LINE.match(line) and current is not None:
            # "{{ח:תת|(ב1)|(1)}}" is a subsection and its first paragraph on one line.
            label = " ".join(filter(None, (render(arg) for arg in first.args)))
            body = render(line[templates[0][1] :])
            # A label with no words is an item whose text was only an editor's note,
            # such as a deleted paragraph: nothing to keep.
            if body:
                # The number of "ת" in the template's name is the level. A definition has
                # no label but is an item of its own; any other unlabeled line continues
                # the one before it.
                labeled = bool(label) or first.named.get("סוג") == "הגדרה"
                current.lines.append(
                    Line(first.name.count("ת"), labeled, f"{label} {body}".strip())
                )
        elif first.name in ("ח:חתימות", "ח:סוף"):
            current = None

    return ParsedLaw(knesset_id, [s for s in sections if s.lines], amendments)
