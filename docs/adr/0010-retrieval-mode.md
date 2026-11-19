# ADR-0010: Vector search is the default retrieval mode

## Status
Accepted. The test split was run once (2026-10-27) and did not change it: the hybrid
modes reached the same Hit@5 as vector search, with a lower MRR.

## Context
ADR-0006 and ADR-0007 added word search and a fusion of the two searches on the assumption
that the fusion would beat vector search alone. The evaluation (56 questions written for it,
39 of them the `dev` split, 32 of those with an answer) measured it. Numbers are the share of
questions with an expected section among the first five results (Hit@5) and MRR within ten.

| Mode | Hit@5 | MRR |
|---|---|---|
| vector | 84% | 0.716 |
| text (Postgres full-text ranking) | 34% | 0.186 |
| bm25 (our own BM25) | 59% | 0.374 |
| hybrid (RRF, Postgres words) | 72% | 0.532 |
| hybrid_bm25 (RRF, BM25, constant 10) | 84% | 0.684 |

A sweep of the RRF constant (5, 10, 20, 40, 60, 100) showed that 10 is better than 60 for
the hybrid with BM25 (MRR 0.684 against 0.593). Seven more variants were declared before the
run and all are reported in `eval/results/2026-10-25-dev-hybrid-variants.md`: weighted RRF,
BM25 with the prefix forms of a word counted as one term, and fusion of normalized scores. The
rule set in advance: a variant counts only if it finds at least two more questions than
vector search at Hit@5, without a worse MRR. None did. The best, normalized fusion with a
weight of 0.7, found the same 27 of 32 questions and had an MRR of 0.744 against 0.716.

## Decision
- **Vector search is the default of `/search` and the only search `/ask` uses.** It was as good
  as every combination measured, and it is the simplest: no word index to keep in memory and to
  build again after an ingest.
- **The other modes stay**, with the names they have in the evaluation: `text`, `bm25`,
  `hybrid`, `hybrid_bm25`. The BM25 index is built when the application starts, and is not
  refreshed until it restarts.
- The default RRF constant is 10, not 60.
- **The test split is run once, at the end, with vector search and with the best hybrid**, to
  say openly whether the finding holds on questions that were not used for choosing. It is
  about 14 questions with an answer, so it cannot settle a difference of one or two questions.

## What the evidence does not say
- It does not say that word search does not help in general. The corpus is about nine hundred
  chunks, the model is multilingual and strong, the questions are in everyday language, and
  only 7 of the dev questions rely on exact numbers or names, which is where word search
  should help. Hebrew prefixes are handled by a rule, not by a morphological analyzer.
- 32 questions: one question is three points. Differences of one or two questions are noise.
- The five questions that vector search misses (late wages, deductions, limitation period,
  court, moving house) are missed by every variant. Four of them use a word of the person that
  is not the word of the law ("late pay" and not "הלנת שכר"). Rewriting the question into the
  law's vocabulary, or reranking, are untested ideas for that.

## Consequences
- `/ask` and `/search` run one query on the database and one embedding of the question.
- ADR-0007 (RRF with k 60, candidates 50) stays correct as a description of the fusion; its
  default constant and its place as the default mode are replaced by this ADR.
