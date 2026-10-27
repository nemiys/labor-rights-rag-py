# Generation evaluation (2026-10-27, model: gemini-3.5-flash-lite, split: all, condition: closed_book)

Questions: 56, of which 46 answerable. Calls that failed: 1.

| Measure | Result |
|---|---|
| Answerable questions answered | 54% (25/46) |
| Answers with every expected fact | 43% (20/46) |
| Answers citing an expected section | not applicable (no sources) |
| Unanswerable questions refused | 60% (6/10) |
| Unanswerable questions answered anyway | 40% (4/10) |
| Mean seconds per question | 2.2 |
| Tokens in / out | 7743 / 6369 |
| Cost in dollars | not priced (a free model) |

## Where the answer was wrong or missing

| Id | Status | Facts | Citation | Question |
|---|---|---|---|---|
| p01 | ERROR HTTPStatusError: 429 from https://generativelanguage.googleapis.com/v1beta/openai/chat/completions: [{
  "error": {
    "code": 429,
    "message": "You exceeded your current quota, please check your  | no | no | אני עובד כבר שנתיים באותו מקום. כמה ימי חופש מגיעים לי בשנה? |
| p02 | refused_by_model | no | no | לא הספקתי לקחת את כל ימי החופש שלי השנה. אפשר להעביר אותם לשנה הבאה? |
| p05 | refused_by_model | no | no | פיטרו אותי מהיום להיום, בלי שום הודעה מראש. מה מגיע לי? |
| p10 | refused_by_model | no | no | מה העונש למי שמטריד מינית בעבודה? |
| p11 | answered | no | no | אני בהריון. המעסיק יכול לפטר אותי? |
| p12 | refused_by_model | no | no | כמה זמן אני יכולה להיעדר מהעבודה אחרי לידה? |
| p14 | refused_by_model | no | no | כמה שעות ביום המעסיק יכול להעסיק אותי בלי שזה ייחשב שעות נוספות? |
| p15 | refused_by_model | no | no | כמה מגיע לי על שעה נוספת בעבודה? |
| p18 | refused_by_model | no | no | אני מועסק דרך חברת כוח אדם אבל עובד בחברה אחרת. אילו זכויות יש לי שם? |
| e01 | refused_by_model | no | no | סעיף 14א לחוק שכר מינימום |
| e03 | answered | no | no | מי נחשב חניך לפי חוק החניכות |
| e04 | refused_by_model | no | no | נטל ההוכחה בתביעה על הטרדה מינית ביחסי עבודה |
| e06 | refused_by_model | no | no | עיצום כספי על מעסיק שהפר את החוק |
| e07 | refused_by_model | no | no | היתר להעסקת עובד זר |
| e09 | refused_by_model | no | no | הממונה על זכויות עובדים זרים |
| e10 | refused_by_model | no | no | ארגון עובדים יציג |
| m01 | answered | no | no | אני בהריון. האם מותר לפטר אותי, וכמה זמן אוכל להיעדר? |
| m03 | refused_by_model | no | no | עבדתי בשבת. מה מגיע לי ומה אומר החוק על עבודה בשבת? |
| m05 | refused_by_model | no | no | התפטרתי כי עברתי דירה. מגיעים לי פיצויים, והאם הייתי צריך להודיע מראש? |
| m06 | refused_by_model | no | no | פיטרו אותי אחרי שהתלוננתי על הטרדה מינית. מה אפשר לעשות? |
| m07 | refused_by_model | no | no | בן 16 רוצה לעבוד. מה הכללים לגבי שעות עבודה ועבודת לילה? |
| m08 | refused_by_model | no | no | כמה ימי חופש מגיעים לי וכמה כסף אקבל על כל יום? |
| m09 | refused_by_model | no | no | חליתי הרבה. האם מותר לפטר אותי, ומה קורה עם דמי המחלה? |
| w02 | answered | no | no | תוך כמה זמן צריך לתבוע שכר שלא שולם? |
| w03 | refused_by_model | no | no | כמה זמן אפשר לתבוע על אפליה בקבלה לעבודה? |
| w06 | answered | no | no | האם מותר לפרסם מודעת דרושים שמחפשת רק גברים? |
| u02 | answered | yes | no | כמה אחוז המעסיק חייב להפריש לפנסיה בשבילי? |
| u05 | answered | yes | no | המעסיק שלי דורש ממני בדיקת פוליגרף. האם זה חוקי? |
| u06 | answered | yes | no | כמה ימי מחלה אפשר לקחת כדי לטפל בילד חולה? |
| u08 | answered | yes | no | האם מותר למעסיק לקרוא את הודעות הווטסאפ שלי? |
