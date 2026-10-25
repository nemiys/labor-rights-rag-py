# ADR-0006: Hebrew text search

## Status
Accepted for development; compared with the alternative in the evaluation (stage 6).

## Context
Vector search understands meaning but not identifiers: the question "סעיף 14א" returned
section 14א of one law and sections numbered 14 of another. Exact terms and numbers
need word search. Postgres has no Hebrew dictionary, and Hebrew words carry prefixes
(ה, ו, ב, כ, ל, מ, ש), so "בחופשה" and "חופשה" look like different words. Checked on
our database: `pg_trgm` recognizes Hebrew letters; the `simple` configuration keeps
"14א" as one token; it splits "התשי״א" in two at the gershayim.

## Decision
- **Normalize in Python, search with Postgres full-text search.** `retrieval/normalize.py`
  removes niqqud and quotation marks, splits on anything that is not a letter or a
  digit, and adds, for each Hebrew word, the form without one prefix letter and
  without two. A prefix is stripped only if at least three letters remain. The
  original word is always kept, so an exact match is never lost.
- **Storage:** `chunks.search_text` (the normalized text of the header and the body,
  filled by the indexing step) and `chunks.tsv`, a generated column
  `to_tsvector('simple', search_text)` with a GIN index.
- **Query:** the question goes through the same normalization, question and function
  words (כמה, מה, לי, של, ...) are dropped, the rest are joined with OR, and results
  are ranked by `ts_rank_cd`. AND would require every word of a natural-language
  question to appear.
- **Domain stopwords.** "סעיף", "סעיפים" and "חוק" are also dropped from the question:
  they are in almost every chunk, and without this the question "סעיף 14א" returned
  sections that mention "סעיף" many times and not section 14א. With it, section 14א of
  both laws that have one comes back first.
- **Scores of different searches are not comparable.** Fusion (stage 4, step 3) uses
  rank, not score.

## Alternatives considered
- **`pg_trgm` only:** handles prefixes and typos without rules, but blurs identifiers
  ("14א" also matches "14" and "4א") and scores poorly for a short question against a
  long chunk.
- **Both:** a second fusion layer without evidence that it is needed. It can be added
  later, since this choice does not lock anything.
- **A Hebrew morphological analyzer:** more accurate, but a heavy dependency for a
  corpus of about a thousand chunks.

## Consequences
- Seen on the real data: a question in plain words ("כמה ימי חופש מגיעים לי") ranks the
  Annual Leave Law second, because the question says "חופש" and the law says "חופשה".
  No word rule joins them; vector search does. A topic that is not in the corpus ("דמי
  הבראה") still returns chunks, since one shared word is enough. Text search alone
  cannot tell that there is no answer.
- The prefix rule is a guess. It can over-match ("מעסיק" also gives "עסיק"); the
  original word stays indexed, and the effect is measured in the evaluation.
- `ts_rank_cd` does not weigh how rare a word is, unlike BM25. If the evaluation shows
  this hurts, ranking can be done in our own code over the matches.
- A change in the normalization rules is applied by running the ingest again: it
  rewrites `search_text` for every chunk and needs no model.
