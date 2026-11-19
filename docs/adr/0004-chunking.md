# ADR-0004: Chunking by section, splitting only long sections

## Status
Accepted

## Context
A chunk is the unit that is embedded, retrieved and quoted. Measured on the 20 laws
(1,045 sections, 2026-10-22): median 209 characters, 90% under 1,010, 99% under
3,072, longest 11,676 (Women's Work Law). Sections over 1,000 characters: 109; over
1,500: 50; over 2,000: 22. A section is also the unit a citizen can look up, so the
verification card cites sections.

## Decision
- **One chunk per section.** A section up to **1,500 characters** is one chunk. The
  limit is a ceiling, not a target size: chunks vary from tens of characters to 1,500.
  It is a starting value, derived from the length distribution above; its effect on
  retrieval was not tested separately in the evaluation.
- **Longer sections are split by the structure the page gives, not guessed from the
  text.** The Open Law Book marks every body line with a template whose name carries
  its level (`ח:תת` subsection, `ח:תתת` paragraph, `ח:תתתת` sub-paragraph). The parser
  keeps that level. Matching `(א)` in the text does not work: the same letter appears
  at several levels, and amendments add `(ג1)`-style subsections.
  1. Cut between subsections (level 2) and group neighbours up to the limit.
  2. A group still over the limit is cut at the next level, and each part starts with
     the lead line of its parent (for example "(ג) עובדת רשאית להיעדר מעבודתה:").
  3. A line without a label continues the line before it and is never a cut point
     (a definition is an item of its own).
  4. Fallback when there are no levels (a list of definitions): cut between lines. A
     single line over the limit stays whole and is reported as an exception.
- **Checked at scale, not by reading.** Rules that must hold for every section of every
  law (no line lost, order kept, size within the limit except reported exceptions,
  every part has its header) are tests over the whole corpus. The ingest report shows
  the distribution of chunk sizes and lists the exceptions.
- **Two texts per chunk.**
  - `text`: the section body only. It is what the verification card quotes, verbatim.
  - `embed_text`: a header (law name, chapter if any, section number and title)
    followed by the body. It is what the embedder sees, so a chunk about "חופשה"
    knows it belongs to the Annual Leave Law. Every part of a split section repeats
    the header.
- **Stored per chunk:** section number, `chunk_index` (0 for an unsplit section),
  the heading path, and the years from the section's `תיקון:` tags.

## Alternatives considered
- **Whole section, never split:** simplest, but a 11,676-character section becomes
  one blurry vector and may exceed the embedding model's input limit.
- **Fixed size with overlap:** ignores the structure of the law, cuts sentences and
  makes the citation unclear.
- **Every subsection a chunk:** precise, but short pieces lose the context of the
  section ("provided that...").
- **Embed the body only:** cleaner, but the vector loses which law it belongs to.

## Consequences
- About 5% of the sections are split, so the threshold affects few chunks. It is a
  single constant; changing it means running the ingest and the evaluation again.
- The quote shown to the user is always a contiguous part of the stored law text.
