# ADR-0003: Law versions, currency check and verification card

## Status
Accepted

## Context
The corpus is a text that changes: Knesset amendments are merged into the Open
Law Book by hand, with a delay. Observed on 2026-10-22 across six laws: the text
matched the latest Knesset publication in four of them; the Annual Leave Law was
merged about two weeks after the Knesset publication; for the Severance Pay Law
the Open Law Book showed a later amendment (2026) than the Knesset field
(January 2025), so the OData field does not always track every amendment.

An answer based on an outdated text can harm a user's rights, and no official
consolidated PDF can be read by a program.

## Decision
- **Stored per law:** MediaWiki `revid`, `content_hash`, last amendment year
  (parsed from the per-section `תיקון:` tags, including Hebrew final letters and
  several years in one tag, ignoring non-year tags such as `ק״ת`), Knesset
  `LatestPublicationDate` and validity. A law whose `revid` and hash did not
  change is not processed again.
- **`currency_status`:** `ok` (dates match), `ahead` (text is newer than the
  Knesset field), `behind` (the Knesset is newer than the text, shown as a
  warning), `unknown`. A `behind` law stays in the corpus but its verification
  card shows a warning.
- **Verification card on every answer, built in code from the database (never by
  the model):** full law name, section number, the verbatim quote, "text current
  as of" date, what to search for on the Knesset site, a link to the law's page in
  the National Legislation Database
  (`.../LawPrimary.aspx?t=lawlaws&st=lawlaws&lawitemid=<OData Id>`, checked in a
  browser for the Hours of Work and Rest Law), a link to the Open Law Book page,
  and the disclaimer: "Not legal advice; the binding text is published in
  Reshumot."
- The Knesset link is shown to the user only. The program never reads it, since
  the site blocks scripts.
- Cited sections must be a subset of the sections that were retrieved.
- Evaluation runs against a frozen snapshot (date and `revid` per law).

## Alternatives considered
- **Trust the Open Law Book without a cross-check:** simple, but a stale law would
  go unnoticed.
- **Use only OData:** official, but it has no text.
- **Let the model write the citation:** easier, but the model can invent or
  alter a quote. A quote taken from the database cannot.
- **Merge Reshumot amendments ourselves:** the most official path, but a large
  and error-prone project with no automatic law-to-file mapping.

## Consequences
- The cross-check detects lag, not correctness: matching dates do not prove the
  text is right.
- First full run (2026-10-22, 20 laws): 15 `ok`, 5 `ahead`, 0 `behind`. In all five
  `ahead` laws the registry's `LatestPublicationDate` is older than an amendment the
  text already includes (for example 2019 against a 2024-25 amendment). A likely
  cause, not verified, is that the field does not follow indirect amendments (made
  by another law). When the registry itself lags, the cross-check cannot detect a
  lagging text, so `ok` is weaker evidence than it looks.
- `ahead` and `behind` need a manual look; they are warnings, not errors.
- A user can always reach the official page in one click.
