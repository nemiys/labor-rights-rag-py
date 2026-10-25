# Hybrid variants on the dev split (2026-10-25)

Seven variants were declared before the run; all are reported. The reading rule, also set
before the run: a variant counts as an improvement only if it finds at least two more
questions than vector search alone at Hit@5, and is not worse at MRR. With 32 questions one
question is 3 points, so differences of one question are noise.

Numbers are questions found out of 32. Recall@5 is the share of expected sections found.

| variant | hit@1 | hit@3 | hit@5 | mrr | recall@5 |
|---|---|---|---|---|---|
| vector alone | 20/32 | 26/32 | 27/32 | 0.716 | 0.79 |
| bm25 alone | 8/32 | 15/32 | 19/32 | 0.374 | 0.47 |
| rrf k=10 (reference) | 18/32 | 24/32 | 27/32 | 0.684 | 0.77 |
| V1 rrf k=10 vector x2 | 20/32 | 25/32 | 27/32 | 0.731 | 0.79 |
| V2 rrf k=10 vector x3 | 21/32 | 25/32 | 27/32 | 0.735 | 0.79 |
| V3 rrf k=10 grouped bm25 | 17/32 | 23/32 | 27/32 | 0.653 | 0.77 |
| V4 rrf k=10 grouped bm25, vector x2 | 20/32 | 25/32 | 27/32 | 0.730 | 0.78 |
| V5 convex a=0.5 | 20/32 | 25/32 | 28/32 | 0.722 | 0.79 |
| V6 convex a=0.7 | 21/32 | 26/32 | 27/32 | 0.744 | 0.80 |
| V7 convex a=0.85 | 20/32 | 27/32 | 27/32 | 0.722 | 0.80 |

Reading: no variant meets the rule. Normalized-score fusion (V5 to V7) is a little better
than unweighted RRF, but within the noise. Grouping the prefix forms of a word into one term
(V3, V4) made BM25 fusion worse. Vector search finds the section in the first five results
for 27 of 32 questions, and the five it misses are missed by every variant.
