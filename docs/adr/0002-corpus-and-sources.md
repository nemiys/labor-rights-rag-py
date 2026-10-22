# ADR-0002: Corpus and allowed sources

## Status
Accepted

## Context
The assistant answers citizens' questions about employment rights in Israel. It
needs the full text of laws in Hebrew, kept current, from sources a program may
legitimately read.

Findings from the source survey (October 2026):
- No free, official, consolidated (amendments merged) text of Israeli laws is
  published by a state body. The Knesset's National Legislation Database shows
  legislative history and amendments as published in Reshumot, and links to the
  consolidated text in the Open Law Book ("לחוק המלא: ספר החוקים הפתוח").
- The Open Law Book (Hebrew Wikisource, run by Hasadna and Wikimedia Israel)
  has the consolidated text, reachable through the MediaWiki API, with a
  per-section amendment tag. Amendments are merged by volunteers, so a law can
  lag behind the latest amendment. It is not an official source.
- The Knesset OData API (`KNS_IsraelLaw`) is official and open, but holds
  metadata only (validity, publication dates), not text.
- `gov.il` HTML pages answer scripts with a Cloudflare challenge (HTTP 403).
  The Knesset website pages also return a JavaScript challenge to scripts.
- Official PDFs exist but are single amendments (Reshumot) or mix old and new
  versions of the same law (`btl.gov.il`).
- Nevo is a commercial legal database.

## Decision
- **Corpus:** about 20 or more Israeli labor laws, defined in `corpus.yaml`.
  The boundary is the topic (employment relations), not a number. A law that is
  not found or does not fit is dropped, with a report.
- **Text source:** Open Law Book via the MediaWiki API, with an identified
  User-Agent, a low request rate and `maxlag`.
- **Validity cross-check:** Knesset OData (`LatestPublicationDate`,
  `LawValidityDesc`). See ADR-0003.
- **Not used as sources:** Nevo, `gov.il` HTML, real-estate and blog sites,
  `btl.gov.il` PDFs. Bot protection is never bypassed.
- **Out of scope:** secondary legislation (regulations, extension orders),
  collective agreements and case law. Many practical rights (for example
  convalescence pay) come from extension orders, so such questions are expected
  to be refused. This is stated in the README.
- **Licensing:** Wikisource text is CC BY-SA 4.0 (attribution required,
  share-alike for derivatives). The official text of a law is generally not
  protected by copyright in Israel, but the editors' layer carries its own
  license. Attribution is shown in the app and the README. Terms are re-checked
  before the repository is made public. The Knesset OData terms of use have not
  been checked yet.

## Alternatives considered
- **FastAPI documentation:** clean and MIT-licensed, but the model already knows
  it from training, so a correct answer does not prove retrieval worked, and it
  gives little differentiation.
- **Official PDFs from `btl.gov.il` or Reshumot:** official, but not consolidated
  and with no reliable mapping from a law to its files.
- **Commercial database (Nevo):** complete and current, but not free and not
  meant for programmatic reuse.
- **Fewer laws (six):** quicker to verify, but the whole corpus might fit in a
  single prompt, which weakens the case for retrieval.

## Consequences
- Answers rest on a non-official source. Every answer carries a verification
  card and a disclaimer (see ADR-0003).
- Wikisource is editable by anyone, so its text is treated as untrusted data in
  the prompt.
- Adding a law is a configuration change, but it must pass the automatic
  validation report before it enters the corpus.
