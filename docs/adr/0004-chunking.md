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
- **One chunk per section.** A section longer than **1,500 characters** is split at
  its top-level subsections, `(א)`, `(ב)`, ... Nested items such as `(1)` never start
  a new chunk. Subsections are grouped in order up to the limit. A single subsection
  longer than the limit stays whole: it is not cut mid-sentence.
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
  single constant and is measured again in the evaluation (stage 6).
- The quote shown to the user is always a contiguous part of the stored law text.
