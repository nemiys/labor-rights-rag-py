# ADR-0011: Exact vector scan at this scale, the HNSW index kept for later

## Status
Accepted.

## Context
The schema has an HNSW index on `chunks.embedding` (ADR-0005). CI failed on a run that
passed on the development machine: the vector search returned one row where two were
expected. Reproduced on an empty database, the same test suite passed on some runs and failed
on others (3 failures in 8 runs), with different tests each time. HNSW is an approximate
search: on a small table, or when many rows were inserted and then rolled back or deleted
(as the tests and the ingest do), it can return fewer rows than asked for. The development
database has 920 real vectors, where the planner took another plan and hid the problem.

An iterative scan (`hnsw.iterative_scan`) was tried first and was not enough: the failures
continued on tests that went through it.

## Decision
- **Vector queries are exact by default.** Each runs `SET LOCAL enable_indexscan = off`, so
  the planner scans the table and sorts by distance. For about a thousand vectors this takes
  milliseconds and returns the true nearest rows every time. Twelve runs on an empty database
  after the change passed every time.
- **The index stays in the schema.** With `VECTOR_INDEX=true` the queries use it, with the
  iterative scan in strict order. It is worth turning on when the corpus is orders of
  magnitude larger.
- Note for whoever changes this: `enable_indexscan = off` does not forbid the index, it only
  makes it very expensive. If the table scan is also disabled, the planner picks the index.

## Alternatives considered
- **Drop the index:** simplest, but loses the way to scale and departs from the plan.
- **Keep it and raise `hnsw.ef_search`:** does not address rows that were deleted.
- **Rebuild the index after each ingest:** would fix the ingest case, not the small tables.

## Consequences
- The vector search time is that of a full scan: about 200 ms for the whole request with the
  question's embedding, of which the embedding is almost all.
- This was found by CI and not by reading: a test environment with real data hides a class of
  problems that an empty database shows.
