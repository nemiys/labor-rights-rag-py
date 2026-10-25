<!-- Second run of the same questions, with nothing changed: it differs from the first by two questions. -->

# Generation evaluation (2026-10-25, model: gemini-3.5-flash-lite, split: dev)

Questions: 39, of which 32 answerable. Calls that failed: 0.

| Measure | Result |
|---|---|
| Answerable questions answered | 81% (26/32) |
| Answers with every expected fact | 78% (25/32) |
| Answers citing an expected section | 75% (24/32) |
| Unanswerable questions refused | 100% (7/7) |
| Unanswerable questions answered anyway | 0% (0/7) |
| Mean seconds per question | 1.5 |
| Tokens in / out | 84719 / 6353 |
| Cost in dollars | not priced (a free model) |

## Where the answer was wrong or missing

| Id | Status | Facts | Citation | Question |
|---|---|---|---|---|
| p07 | refused_by_model | no | no | המשכורת שלי מגיעה באיחור כל חודש. מה אפשר לדרוש מהמעסיק? |
| p10 | answered | yes | no | מה העונש למי שמטריד מינית בעבודה? |
| p16 | refused_by_model | no | no | המעסיק ניכה לי כסף מהמשכורת בלי לשאול אותי. האם זה חוקי? |
| m01 | answered | no | yes | אני בהריון. האם מותר לפטר אותי, וכמה זמן אוכל להיעדר? |
| m05 | refused_by_model | no | no | התפטרתי כי עברתי דירה. מגיעים לי פיצויים, והאם הייתי צריך להודיע מראש? |
| m08 | refused_by_model | no | no | כמה ימי חופש מגיעים לי וכמה כסף אקבל על כל יום? |
| m10 | answered | yes | no | החברה שבה אני עובד קורסת ולא שילמה לי משכורות. מה קורה עם החוב? |
| w01 | refused_by_model | no | no | כמה זמן יש לי להגיש תביעה על חופשה שלא קיבלתי? |
| w04 | refused_by_model | no | no | איזה בית משפט דן בסכסוך על הודעה מוקדמת בין עובד למעסיק? |
