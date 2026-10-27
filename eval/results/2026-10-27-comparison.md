<!-- The same model (gemini-3.5-flash-lite) and the same 56 questions in three conditions. "system" is the dev run 2 of 2026-10-25 for the dev questions and the single test run of 2026-10-27 for the test questions. Two calls failed on infrastructure (a quota error in closed_book p01, a connection error in all_laws p07) and were run again; their second results are used. -->

# Comparison of the three conditions (2026-10-27)

Answerable questions: 46 (32 dev, 14 test). Unanswerable: 10 (7 dev, 3 test).

| Condition | Answered | Every expected fact | Cites an expected section | Unanswerable refused |
|---|---|---|---|---|
| no retrieval | 26 of 46 | 20 of 46 | not applicable | 6 of 10 |
| the system (5 sections found) | 37 of 46 | 35 of 46 | 33 of 46 | 9 of 10 |
| all laws in the prompt | 44 of 46 | 43 of 46 | 43 of 46 | 9 of 10 |

By split:

| Split | Condition | Answered | Every expected fact | Cites | Refused |
|---|---|---|---|---|---|
| dev (32 + 7) | no retrieval | 21 | 17 | n/a | 4 of 7 |
| dev | system | 26 | 25 | 24 | 7 of 7 |
| dev | all laws | 30 | 29 | 29 | 7 of 7 |
| test (14 + 3) | no retrieval | 5 | 3 | n/a | 2 of 3 |
| test | system | 11 | 10 | 9 | 2 of 3 |
| test | all laws | 14 | 14 | 14 | 2 of 3 |

Cost of getting there (free model, tokens in):

| Condition | Tokens in, 56 questions | Mean seconds per question |
|---|---|---|
| no retrieval | 7.7 thousand | 2.2 |
| the system | about 123 thousand (dev 84.7 and test 38.2) | 1.5 |
| all laws | 14.0 million (about 255 thousand each) | 7.3 |

Questions the system missed (not answered, or a fact missing) and all laws got: p06, p07, p12,
p16, m03, m05, m06, m08, w01, w04. All laws missed and the system got: e05 (the answer had no
citation), w02 (refused).

Caveats: one model that is not deterministic; the system numbers come from two different runs;
a difference of one or two questions is noise. In "no retrieval", a question the corpus cannot
answer counts as answered when the model answers it, even if the answer is right (it may know
a right that comes from an extension order).
