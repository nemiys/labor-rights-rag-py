<!-- The first run, before any tuning: the baseline every later change is compared with. Dev split only. -->

# Retrieval evaluation (2026-10-25, split: dev, 32 answerable questions)

A chunk counts when it belongs to an expected section. Hit@k: the share of questions with such a chunk in the first k. MRR is within the first 10. Recall@5: the share of the expected sections found in the first 5.

| Mode | Hit@1 | Hit@3 | Hit@5 | MRR | Recall@5 |
|---|---|---|---|---|---|
| vector | 62% | 81% | 84% | 0.716 | 79% |
| text | 9% | 22% | 34% | 0.186 | 24% |
| hybrid | 44% | 56% | 72% | 0.532 | 61% |

## By question type (Hit@5 / MRR)

| Type | n | vector | text | hybrid |
|---|---|---|---|---|
| exact_term | 7 | 100% / 0.90 | 43% / 0.17 | 86% / 0.58 |
| multi_section | 7 | 86% / 0.64 | 57% / 0.39 | 71% / 0.71 |
| paraphrase | 14 | 86% / 0.76 | 21% / 0.07 | 79% / 0.48 |
| wording_differs | 4 | 50% / 0.38 | 25% / 0.25 | 25% / 0.29 |

## Hybrid misses: not in the first 5 (9)

| Id | vector | text | hybrid | Question |
|---|---|---|---|---|
| p07 | - | - | - | המשכורת שלי מגיעה באיחור כל חודש. מה אפשר לדרוש מהמעסיק? |
| p14 | 3 | - | - | כמה שעות ביום המעסיק יכול להעסיק אותי בלי שזה ייחשב שעות נוספות? |
| p16 | - | - | - | המעסיק ניכה לי כסף מהמשכורת בלי לשאול אותי. האם זה חוקי? |
| e01 | 1 | - | - | סעיף 14א לחוק שכר מינימום |
| m04 | 3 | - | - | המעסיק לא משלם לי שכר מינימום. איך תובעים ומה הוא עלול לקבל? |
| m05 | 6 | - | - | התפטרתי כי עברתי דירה. מגיעים לי פיצויים, והאם הייתי צריך להודיע מראש? |
| w01 | - | - | - | כמה זמן יש לי להגיש תביעה על חופשה שלא קיבלתי? |
| w02 | 2 | - | 7 | תוך כמה זמן צריך לתבוע שכר שלא שולם? |
| w04 | - | - | - | איזה בית משפט דן בסכסוך על הודעה מוקדמת בין עובד למעסיק? |

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
