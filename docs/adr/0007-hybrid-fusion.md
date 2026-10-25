# ADR-0007: Combining vector and text search with RRF

## Status
Partly superseded by ADR-0010: the evaluation showed no gain over vector search, so
hybrid is not the default, and the constant `k` is 10 and not 60. The description of the
fusion below is still how it works.

## Context
Vector search and text search each fail where the other works (ADR-0006): the vector
finds "כמה ימי חופש מגיעים לי" in the Annual Leave Law and misses "סעיף 14א"; the text
search finds "סעיף 14א" and misses "חופש" against "חופשה". Their scores cannot be added:
cosine similarity stays in a narrow band (about 0.5 to 0.7), while `ts_rank_cd` is
unbounded and changes from question to question (0.1 for the best hit of one question,
2.8 for another).

## Decision
- **Reciprocal Rank Fusion.** Each search gives its ranked list; a chunk's score is the
  sum over the lists it appears in of `1 / (k + rank)`. Only ranks are used, never scores.
  A chunk found by both searches beats a chunk found by one.
- **`k = 60`** (the value common in the literature), a setting (`RRF_K`).
- **Each search returns 50 candidates** (`SEARCH_CANDIDATES`) before the fusion, never
  fewer than the `k` the caller asked for.
- **Ties** go to the chunk with the better single rank, then to the lower id, so the
  result is the same on every run.
- **`/search?mode=hybrid` is the default.** Each hit also carries its rank in each search
  (`vector_rank`, `text_rank`, empty when that search did not find it), to see in the
  debugging and in the evaluation which search brought it.

## Alternatives considered
- **A weighted sum of normalized scores:** uses the size of a score, but the scales
  differ and move between questions, so one weight would behave differently for each,
  and it needs tuning.
- **A reranking model on top:** a separate decision (stage 4 does not include it).

## Consequences
- The fusion cannot say "there is no answer": it always returns the best of what the
  two searches found. Refusal is decided in stage 5.
- `k` is not tuned yet. The evaluation compares several values.
