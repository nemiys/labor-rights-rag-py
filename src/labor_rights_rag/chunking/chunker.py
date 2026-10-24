"""Cut a parsed section into chunks. See docs/adr/0004-chunking.md for the rules."""

from collections.abc import Sequence
from dataclasses import dataclass

from labor_rights_rag.parsing.wikitext import Line, Section

MAX_CHARS = 1500
FIRST_SPLIT_LEVEL = 2  # subsections: "(א)"
LAST_LEVEL = 6  # the pages use up to level 5; past this we cut between lines


@dataclass(frozen=True)
class Chunk:
    section_number: str
    chunk_index: int  # 0 for a section that was not split
    text: str  # the body only: this is what the verification card quotes
    embed_text: str  # header + parents' lead lines + body: this is what the embedder sees
    heading_path: str  # the header on its own
    amended_years: list[int]


@dataclass(frozen=True)
class Part:
    """A piece of a section. `context` repeats the lead lines of its parents for the
    embedder only: the quote is `lines`, a contiguous piece of the law."""

    context: list[Line]
    lines: list[Line]


def build_heading(law_name: str, section: Section) -> str:
    """The header that is put before the body in `embed_text`."""
    parts = [law_name]
    if section.chapter:
        parts.append(section.chapter)
    parts.append(f"{section.number}. {section.title}")
    return "\n".join(parts)


def size(lines: Sequence[Line]) -> int:
    return len("\n".join(line.text for line in lines))


def split_into_blocks(lines: Sequence[Line], level: int) -> list[list[Line]]:
    """A block starts at a labeled line of this level or higher. Deeper lines and lines
    without a label stay in the block they follow."""
    blocks: list[list[Line]] = []
    for line in lines:
        starts = line.labeled and 0 < line.level <= level
        if starts or not blocks:
            blocks.append([])
        blocks[-1].append(line)
    return blocks


def group_blocks(blocks: list[list[Line]], max_chars: int) -> list[list[Line]]:
    """Join neighbouring blocks while they fit. A group over the limit is one block."""
    groups: list[list[Line]] = []
    for block in blocks:
        if groups and size(groups[-1] + block) <= max_chars:
            groups[-1] = groups[-1] + block
        else:
            groups.append(list(block))
    return groups


def split_lines(
    lines: Sequence[Line],
    max_chars: int,
    context: Sequence[Line] = (),
    level: int = FIRST_SPLIT_LEVEL,
) -> list[Part]:
    # Fits, or a single line that cannot be cut: it stays whole (reported as an exception).
    if size(lines) <= max_chars or len(lines) == 1:
        return [Part(list(context), list(lines))]

    if level > LAST_LEVEL:
        blocks = [[line] for line in lines]
    else:
        blocks = split_into_blocks(lines, level)
    if len(blocks) == 1:
        return split_inside(lines, max_chars, context, level)

    parts: list[Part] = []
    for group in group_blocks(blocks, max_chars):
        if size(group) > max_chars:  # one block that is still too long
            parts += split_inside(group, max_chars, context, level)
        else:
            parts.append(Part(list(context), group))
    return parts


def split_inside(
    block: Sequence[Line], max_chars: int, context: Sequence[Line], level: int
) -> list[Part]:
    """Cut a block at the next level. Its first line leads the first part and is
    repeated as context in the others."""
    lead, body = block[0], block[1:]
    budget = max(max_chars - len(lead.text) - 1, 1)  # the lead takes room in the first part
    parts = split_lines(body, budget, [*context, lead], level + 1)
    parts[0] = Part(list(context), [lead, *parts[0].lines])
    return parts


def chunk_section(law_name: str, section: Section, max_chars: int = MAX_CHARS) -> list[Chunk]:
    heading = build_heading(law_name, section)
    chunks: list[Chunk] = []
    for index, part in enumerate(split_lines(section.lines, max_chars)):
        text = "\n".join(line.text for line in part.lines)
        context = "".join(line.text + "\n" for line in part.context)
        chunks.append(
            Chunk(
                section_number=section.number,
                chunk_index=index,
                text=text,
                embed_text=f"{heading}\n{context}{text}",
                heading_path=heading,
                amended_years=section.amended_years,
            )
        )
    return chunks
