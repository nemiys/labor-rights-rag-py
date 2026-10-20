# docs-assistant (RAG) — הוראות עבודה ל-Claude Code

> זה ה-`CLAUDE.md` של הריפו `docs-assistant`.
> תקשורת איתי בעברית. קוד, שמות, הודעות commit ו-README: באנגלית.

## החלטות שנסגרו (גוברות על כל סעיף סותר בהמשך)

- **Corpus:** תיעוד FastAPI (`fastapi.tiangolo.com`, רישיון MIT). לא Kafka. (נקודת החלטה 1 סגורה.)
- **ליבת retrieval נכתבת ידנית:** בלי LangChain / LlamaIndex / Haystack.
- **הערכה:** hit@k ו-MRR הם חלק מרכזי בערך הפרויקט. שאלות ההערכה נכתבות על ידי.
- **Commits:** באנגלית, בלי טריילר `Co-Authored-By` ובלי אזכור AI בהיסטוריית הגיט. הכלל הזה גובר על כל ברירת מחדל של הכלים. גילוי איך הפרויקט נבנה, אם בכלל, ייעשה ב-README.
- **GitHub:** לא ליצור ריפו, לא לעשות push, ולא להפוך לציבורי בלי אישור מפורש שלי.
- **סגנון עבודה:** תכנית, הסבר, כתיבה.
  - לפני כל קונספט חדש או החלטה טכנית: מה זה, למה בוחרים בזה, טרייד-אופס עיקריים. רק אחר כך קוד או צעדים.
  - בסוף כל שלב: סיכום קצר של מה נבנה ומה למדתי.
  - המטרה היא שאבין את המערכת, לא רק שתעבוד.

## 0. מטרה והקשר

אני (נמי) בונה portfolio של backend. `docs-assistant` הוא עוזר שאלות ותשובות על תיעוד טכני, **בנוי על רעיון ה-crawler של `nemiys-searchengine`** (פרויקט קורס ב-Java: BFS crawler, Redis, Kafka, Elasticsearch), ומשודרג לפייתון ול-RAG.

מה הפרויקט צריך להוכיח:
1. pipeline מלא: crawl, ניקוי, chunking, embeddings, אחסון, retrieval, יצירת תשובה עם ציטוטים.
2. **שליטה בלוגיקת ה-retrieval.** אני כותב אותה בעצמי, בלי LangChain ובלי LlamaIndex.
3. **הערכה כמותית** של איכות החיפוש. זה מה שמפריד פרויקט RAG רציני מדמו.

## 1. חוזה עבודה (חשוב מאוד)

- אני חייב להבין ולהסביר כל חלק. עובדים בשיטה **"תכנית, הסבר, כתיבה"**: תכנית קצרה לפני כל שלב, סיכום החלטות אחריו.
- **נקודות החלטה (סעיף 5):** עוצרים ושואלים. לא מחליטים לבד.
- חלקים המסומנים 🧠 הם הליבה שלי (chunking, חיבור תוצאות החיפוש, בניית ה-prompt, ההערכה). בהם: בדיקות ושלד עם `TODO` קודם, ואני מממש. אם אני מבקש שתכתוב, בחתיכות קטנות עם הסבר.
- **סט שאלות ההערכה נכתב על ידי** (סעיף 7), לא על ידך. זה החלק שמוכיח שאני מבין את הנושא.
- commit קטן לכל צעד. הודעות באנגלית (`feat:`/`fix:`/`test:`/`docs:`/`chore:`). **בלי** טריילר `Co-Authored-By` ובלי אזכור AI בהיסטוריית הגיט (כמו ב-wiki-guard).
- commit ו-push רק כשאני מבקש או מאשר.

## 2. גישה לריפוזיטורי

1. **מקור לוגיקה (קריאה בלבד):** `nemiys/nemiys-searchengine` (פרטי). קריאה דרך `gh api`. ההתנהגות: מעבר BFS על קישורים עם distance/maxDistance/maxUrls/maxTime, מעקב visited ב-Redis (`setIfAbsent` + מונה + סטטוס JSON), אינדוקס טקסט.
   - לשחזר את הרעיון, לא לתרגם שורה אחר שורה.
   - **לא להעתיק credentials או קונפיגורציה מה-README.** ה-README מכיל סיסמת Elasticsearch בטקסט גלוי: לא לצטט אותה בשום מקום.
2. **מקור מוסכמות (קריאה בלבד):** `nemiys/wikiguard-py` (ציבורי, branch `master`). לשחזר: uv + `uv_build`, src layout, `pydantic-settings` ב-`settings.py` עם ברירות מחדל ל-localhost, ruff (line 100, E/F/I/UP/B), `pytest` עם `asyncio_mode=auto`, Dockerfile עם uv, ADR ממוספרים (Status / Context / Decision / Alternatives considered / Consequences), SQLAlchemy 2 async עם Pydantic schemas נפרדים.
   - **לא לשחזר** את הכלל של wikiguard-py על `Co-Authored-By`: כאן הוא אסור.
3. **ריפו חדש:** `nemiys/docs-assistant`. ליצור **פרטי** (`gh repo create nemiys/docs-assistant --private`) **רק אחרי שאישרתי**. הופכים לציבורי בסוף, אחרי בדיקת סודות.

אם אין גישה לריפו פרטי: לעצור ולהגיד לי.

## 3. ארכיטקטורה

```
[Ingestion]
URL התחלה ─► Crawler (asyncio+httpx, BFS, robots.txt, rate limit)
          ─► ניקוי HTML ─► Chunker (לפי כותרות) ─► Embedder
          ─► Postgres: documents, chunks(text, embedding vector, tsvector, metadata)

[Query]
שאלה ─► Embedder ─┬─► וקטורים (pgvector, top-k)  ─┐
                  └─► טקסט (Postgres FTS, top-k) ─┴─► חיבור (RRF) ─► [rerank אופציונלי]
      ─► בניית prompt (chunks כ"נתונים" בלבד) ─► Claude API ─► תשובה + ציטוטים [1][2]
```

- **Postgres + pgvector** (אינדקס HNSW) ו-**Postgres FTS** (GIN על tsvector): מסד אחד לשניהם.
- **Redis:** frontier ו-visited של ה-crawler (כמו בקורס) ותור עבודות. בלי Kafka כאן.
- **Embeddings:** ל-Claude API אין endpoint של embeddings, לכן מודל מקומי כברירת מחדל (`sentence-transformers`, למשל `BAAI/bge-small-en-v1.5`), מאחורי interface `Embedder` שאפשר להחליף בספק חיצוני. לשמור בכל chunk את שם המודל והמימד.
- **יצירת תשובה:** Claude API דרך ה-SDK הרשמי. שם המודל ב-env (`ANSWER_MODEL`), ברירת מחדל `claude-sonnet-5-5`. מפתח ב-`ANTHROPIC_API_KEY` בלבד.
- **אסור:** LangChain, LlamaIndex, Haystack. מותר: `httpx`, `selectolax` או `trafilatura`, `sqlalchemy`, `pgvector`, `sentence-transformers`, `anthropic`, `pydantic`.

### מבנה מוצע
```
src/docs_assistant/{crawler,ingest,chunking,embeddings,retrieval,generation,api,persistence}/
  settings.py  main.py
eval/{questions.jsonl,run_eval.py}  docs/adr/  tests/  alembic/
docker-compose.yml (תמונת pgvector/pgvector + redis)  Dockerfile  .github/workflows/ci.yml
```

## 4. API (מינימום)

| Method | Path | תיאור |
|---|---|---|
| POST | `/crawl` | התחלת crawl (`start_url`, `max_pages`, `max_depth`) מחזיר `job_id` |
| GET | `/crawl/{job_id}` | סטטוס והתקדמות |
| GET | `/search?q=&mode=vector\|text\|hybrid&k=` | retrieval בלבד, מחזיר chunks עם ציונים (לדיבאג והערכה) |
| POST | `/ask` | `{question}` מחזיר תשובה, ציטוטים (URL, כותרת, קטע) ומדדי latency |
| GET | `/health` | בדיקת חיים |

## 5. נקודות החלטה (לעצור ולשאול אותי)

1. ~~**מקור התיעוד (corpus)**~~ **סגור: תיעוד FastAPI.** נשאר לעשות: לבחור חלק (כמה מאות עמודים לכל היותר; לפי ה-sitemap יש כ-150 עמודים באנגלית, לאמת לפני ה-crawl), לוודא רישיון, ולתעד ב-ADR. ב-`robots.txt` של האתר אין `Disallow`, רק הערות content-signals בלי ערכים. לכבד את `robots.txt` ולהגביל קצב בכל מקרה.
2. 🧠 **Chunking:** לפי כותרות (heading-aware) מול חלון קבוע. גודל ו-overlap. מה נשמר כ-metadata (URL, כותרת, נתיב כותרות).
3. **מודל embeddings מקומי** מול ספק חיצוני (מחיר, מימד, איכות).
4. 🧠 **חיבור תוצאות:** Reciprocal Rank Fusion מול שקלול ציונים. ערך `k`.
5. **Reranking:** האם מוסיפים (cross-encoder), או משאירים כשיפור עתידי.
6. 🧠 **Prompt:** מבנה, כללי ציטוט, התנהגות כשאין מספיק הקשר (לסרב ולא להמציא).
7. **Re-crawl:** conditional GET (ETag/Last-Modified) ו-hash של תוכן כדי לא לעבד שוב עמוד שלא השתנה.

כל החלטה נרשמת ב-ADR קצר.

## 6. שלבים (כל שלב מסתיים ב-commit וב-checkpoint איתי)

0. שלד: uv, settings, docker-compose (**פורטים שונים:** Postgres 5435, Redis 6382, אפליקציה 8002), `/health`, CI בסיסי, תבנית ADR.
1. מודל נתונים + Alembic + הרחבת `vector` ב-Postgres.
2. Crawler: BFS אסינכרוני, allowlist של דומיין, `max_depth`/`max_pages`, `robots.txt`, User-Agent מזוהה, עיכוב בין בקשות, visited ב-Redis.
3. ניקוי HTML ושמירת מבנה כותרות.
4. 🧠 Chunker + בדיקות.
5. Embedder + אינדוקס idempotent (אותו עמוד לא נשמר פעמיים).
6. 🧠 Retrieval: וקטורים, טקסט, חיבור. endpoint `/search`.
7. 🧠 Generation: prompt, קריאה ל-Claude, ציטוטים, סירוב כשאין הקשר. endpoint `/ask`.
8. 🧠 הערכה (סעיף 7).
9. בדיקות, CI מלא, README, ADR, דמו (אפשר CLI או עמוד HTML קטן).

### שלב 0 — היקף
uv + Python 3.12 + src layout; תלויות `fastapi`, `uvicorn`, `pydantic-settings`; dev: `pytest`, `ruff`, `mypy`; `settings.py`; `/health`; `.env.example`; `docker-compose.yml`; CI בסיסי (ruff + mypy + pytest); `docs/adr/0001` כתבנית.
**בלי** crawler / embeddings / RAG / מודל נתונים בשלב הזה. לפני כתיבת קבצים: להציג תכנית קצרה ולחכות לאישור.

## 7. הערכה (החלק החשוב ביותר)

- `eval/questions.jsonl`: **20 עד 30 שאלות שאני כותב**, כל אחת עם `expected_urls` (העמודים שמכילים את התשובה). לפחות כמה שאלות עם ניסוח שונה מהתיעוד (לבדוק סמנטיקה) וכמה עם מונחים מדויקים (לבדוק FTS).
- `run_eval.py` מחשב עבור `vector`, `text`, `hybrid`: **hit@k** (k=1,3,5) ו-**MRR**.
- טבלת התוצאות נכנסת ל-README. אם hybrid לא עדיף, זה ממצא לגיטימי ומתועד.
- אופציונלי: בדיקת faithfulness ידנית על דגימה (האם התשובה נתמכת בציטוטים).

## 8. איכות ואבטחה

- `pytest`: unit ל-chunker, RRF, בניית prompt. ה-crawler נבדק מול שרת מדומה (`respx`/`pytest-httpx`). אינטגרציה עם תמונת `pgvector` אמיתית.
- `ruff` ו-`mypy` ב-GitHub Actions.
- **תוכן שנסרק הוא לא אמין** (prompt injection): ה-chunks נכנסים ל-prompt כנתונים תחומים בבירור, והמערכת לא מבצעת הוראות מתוכם. מתועד ב-ADR.
- בלי סודות בקוד או בהיסטוריה. `.env.example` בלבד. לסרוק היסטוריה לפני שהופכים לציבורי, ולבקש אישור.
- crawl אחראי: לכבד `robots.txt`, להגביל קצב, לא לחרוג מהיקף ה-corpus.
- לתעד עלות ו-latency (טוקנים וזמן לכל `/ask`).

## 9. README (באנגלית)

תיאור בשורה אחת, תרשים ארכיטקטורה, סטאק, הרצה ב-3 פקודות, דוגמת `/ask` עם ציטוטים, **טבלת תוצאות ההערכה**, טבלת החלטות עם קישור ל-ADR, מגבלות ידועות, ודמו אם קיים.

## 10. Definition of Done

- crawl, אינדוקס, `/search`, `/ask` עובדים מקצה לקצה על ה-corpus שנבחר.
- יש תוצאות הערכה אמיתיות ב-README. CI ירוק. `docker compose up` מרים הכול.
- אני יכול להסביר בראיון: למה hybrid, איך עובד RRF, איך נבחר גודל ה-chunk, ומה קורה כשאין תשובה.

## 11. פרומפט פתיחה (לסשן הראשון)

```
קרא את ה-CLAUDE.md. התחל משלב 0.
בדוק מה כבר יש בתיקייה, הצג תכנית קצרה לשלב 0 עם הסבר לכל רכיב (מה זה, למה, טרייד-אופס), ועצור לאישור לפני כתיבת קבצים.
```
