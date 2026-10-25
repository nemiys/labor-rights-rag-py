<!-- Dev split, vector search, threshold 0.5, free model. The retrieval table at the top is from this run; the first baseline is in 2026-10-25-dev-baseline.md. -->

# Retrieval evaluation (2026-10-25, split: dev, 32 answerable questions)

A chunk counts when it belongs to an expected section. Hit@k: the share of questions with such a chunk in the first k. MRR is within the first 10. Recall@5: the share of the expected sections found in the first 5.

| Mode | Hit@1 | Hit@3 | Hit@5 | MRR | Recall@5 |
|---|---|---|---|---|---|
| vector | 62% | 81% | 84% | 0.716 | 79% |
| text | 9% | 22% | 34% | 0.186 | 24% |
| bm25 | 25% | 47% | 59% | 0.374 | 47% |
| hybrid | 44% | 66% | 75% | 0.564 | 67% |
| hybrid_bm25 | 56% | 75% | 84% | 0.684 | 77% |

## By question type (Hit@5 / MRR)

| Type | n | vector | text | bm25 | hybrid | hybrid_bm25 |
|---|---|---|---|---|---|---|
| exact_term | 7 | 100% / 0.90 | 43% / 0.17 | 100% / 0.67 | 86% / 0.61 | 100% / 0.86 |
| multi_section | 7 | 86% / 0.64 | 57% / 0.39 | 71% / 0.38 | 71% / 0.73 | 86% / 0.67 |
| paraphrase | 14 | 86% / 0.76 | 21% / 0.07 | 43% / 0.25 | 79% / 0.53 | 86% / 0.70 |
| wording_differs | 4 | 50% / 0.38 | 25% / 0.25 | 25% / 0.28 | 50% / 0.31 | 50% / 0.36 |

## Misses of hybrid_bm25: not in the first 5 (5)

| Id | vector | text | bm25 | hybrid | hybrid_bm25 | Question |
|---|---|---|---|---|---|---|
| p07 | - | - | - | - | - | המשכורת שלי מגיעה באיחור כל חודש. מה אפשר לדרוש מהמעסיק? |
| p16 | - | - | - | - | - | המעסיק ניכה לי כסף מהמשכורת בלי לשאול אותי. האם זה חוקי? |
| m05 | 6 | - | - | - | - | התפטרתי כי עברתי דירה. מגיעים לי פיצויים, והאם הייתי צריך להודיע מראש? |
| w01 | - | - | - | - | 9 | כמה זמן יש לי להגיש תביעה על חופשה שלא קיבלתי? |
| w04 | - | - | 9 | - | 9 | איזה בית משפט דן בסכסוך על הודעה מוקדמת בין עובד למעסיק? |

## Refusal threshold (closest-chunk similarity)

What a refusal below each value would do. The current setting is 0.5.

| Threshold | Answerable refused | Unanswerable passed to the model |
|---|---|---|
| 0.40 | 0% | 100% |
| 0.45 | 0% | 100% |
| 0.50 | 0% | 86% |
| 0.55 | 3% | 57% |
| 0.60 | 6% | 0% |
| 0.65 | 34% | 0% |
| 0.70 | 75% | 0% |

# Generation evaluation (2026-10-25, model: gemini-3.5-flash-lite, split: dev)

Questions: 39, of which 32 answerable. Calls that failed: 0.

| Measure | Result |
|---|---|
| Answerable questions answered | 75% (24/32) |
| Answers with every expected fact | 72% (23/32) |
| Answers citing an expected section | 72% (23/32) |
| Unanswerable questions refused | 100% (7/7) |
| Unanswerable questions answered anyway | 0% (0/7) |
| Mean seconds per question | 1.3 |
| Tokens in / out | 84719 / 5240 |
| Cost in dollars | not priced (a free model) |

## Where the answer was wrong or missing

| Id | Status | Facts | Citation | Question |
|---|---|---|---|---|
| p07 | refused_by_model | no | no | המשכורת שלי מגיעה באיחור כל חודש. מה אפשר לדרוש מהמעסיק? |
| p16 | refused_by_model | no | no | המעסיק ניכה לי כסף מהמשכורת בלי לשאול אותי. האם זה חוקי? |
| e10 | refused_by_model | no | no | ארגון עובדים יציג |
| m01 | answered | no | yes | אני בהריון. האם מותר לפטר אותי, וכמה זמן אוכל להיעדר? |
| m05 | refused_by_model | no | no | התפטרתי כי עברתי דירה. מגיעים לי פיצויים, והאם הייתי צריך להודיע מראש? |
| m08 | refused_by_model | no | no | כמה ימי חופש מגיעים לי וכמה כסף אקבל על כל יום? |
| m10 | answered | yes | no | החברה שבה אני עובד קורסת ולא שילמה לי משכורות. מה קורה עם החוב? |
| w01 | refused_by_model | no | no | כמה זמן יש לי להגיש תביעה על חופשה שלא קיבלתי? |
| w02 | refused_by_model | no | no | תוך כמה זמן צריך לתבוע שכר שלא שולם? |
| w04 | refused_by_model | no | no | איזה בית משפט דן בסכסוך על הודעה מוקדמת בין עובד למעסיק? |
