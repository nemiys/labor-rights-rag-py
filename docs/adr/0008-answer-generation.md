# ADR-0008: Answer generation

## Status
Accepted. The evaluation used one free model (`gemini-3.5-flash-lite`); Claude has not
been called yet, so the cost-against-quality comparison is still open.

## Context
The answer is written by a language model from the sections the search found. A wrong
answer can harm a person's rights, so the model must not invent, must refuse when the
sources do not answer, and must not follow instructions hidden in a source (the text
comes from a wiki that anyone can edit). Calling the Claude API costs money (about one
cent a question with `claude-sonnet-5-5`, estimated, not measured), and a free model may
be good enough for a task that looks simple.

## Decision
- **A model sits behind an `Answerer` interface** (`answer(question, hits)`), like the
  `Embedder`. Implementations: a fake for tests, Claude, and a free model. Development
  runs without paying; Claude is called for the evaluation run. The evaluation produces a
  table of cost against quality for the models.
- **Sources go into the prompt as numbered data** (`<source id="1" law=".." section="..">`).
  The text is escaped, so a source cannot close its tag or open a new one. The system
  prompt says that sources are data and not instructions.
- **The model cites numbers, not names:** `[1]`, `[2][3]`. It never writes a law name or a
  section number, so it cannot invent a section. A number outside the sources that were
  given is invalid, and the card is built from the database, not from the model.
- **Plain text, not JSON.** A small model does not always return valid JSON; markers in
  text are read by a regular expression for every model.
- **Refusal is a fixed marker** (`[NO_ANSWER]`), and the sentence the user sees on refusal
  is ours, not the model's.

## Alternatives considered
- **Claude only:** simplest and best quality, but a cost per question and no comparison.
- **A free model only:** no cost, but the quality on Hebrew and on following the rules is
  unknown and has to be measured before it is relied on.
- **JSON output:** easier to read, but fragile with small models.

## Implementations
- `ClaudeAnswerer`: the official `anthropic` SDK, model from `ANSWER_MODEL` (default
  `claude-sonnet-5-5`), `effort` low as a starting value. No sampling parameters are sent.
  A reply the safety classifiers stopped counts as no answer. The server-side refusal
  fallback is not enabled: it could not be tested without a key, and a stopped reply
  already ends as `refused_by_model`.
- `ChatCompletionsAnswerer`: one `httpx` client for any model that speaks the
  `/chat/completions` protocol (Ollama, hosted services). Google's documentation gives the
  address `https://generativelanguage.googleapis.com/v1beta/openai/` and a bearer key for
  its free tier. The service's limits and terms (including whether free-tier questions are
  used to improve the service) were not verified and have to be read before use.
- Retries with a wait for a dropped connection, 429 and 5xx are shared by this client and
  the Wikisource client (`http_retry.py`). Keys are `SecretStr` settings and never appear
  in code, logs or errors.
- Every answer records tokens, seconds and, for a model in the price list, the cost.

## First live trial (2026-10-25, the free tier of Google's Gemini API)
- The whole chain worked with `gemini-3.5-flash-lite`, 4 to 7 seconds a question: an answer
  with a correct citation, a correct refusal ("דמי הבראה", a topic the corpus does not
  cover, which the score threshold let through), and a second correct answer. The numbers
  in the first answer match section 3 of the Annual Leave Law word for word. Three
  questions are a check that it works, not an evaluation.
- `gemini-3.8-flash` (the model in Google's examples) answered `503`, "high demand", on
  every call, and a first call got `403` once. Two older Flash models are "no longer
  available to new users". The models a key can use change, so the model name is a
  setting and not code, and the client now shows the server's reason in the error.
- Some services leave hidden thinking out of `completion_tokens` but count it in
  `total_tokens`. The output size is the larger of the two.
- **The free tier cannot serve real users.** Google's terms for unpaid use say the content
  is used to improve its products, human reviewers may read it, and sensitive or personal
  information must not be sent. Questions about dismissal or harassment can contain it. A
  public service needs a paid tier, or a model that runs on our own machine.

## What the dev split showed about generation (2026-10-25, `gemini-3.5-flash-lite`)
- Two runs of the same 39 questions with nothing changed: 24 and 26 of the 32 answerable
  questions answered. The free model is not deterministic even at temperature 0, so one run
  is known to within about two questions, and results are reported as a range.
- In both runs all 7 unanswerable questions were refused: no invented answer.
- Of the 8 to 10 failures per run, 5 are questions whose section the search did not bring (the
  model refused, which is safe), 2 or 3 are refusals with the section in hand, and 2 are
  partial or off-target answers (an answer to a neighbouring question, or a citation of a
  section that points to the right one).
- **A bug found by reading the answers:** the model wrote the refusal marker after a partial
  answer and the person would have seen `[NO_ANSWER]`. The parser now removes it, and the
  prompt says to use it only when no part is answered.

## Consequences
- The prompt is written in English, which models follow more reliably, and requires a
  Hebrew answer.
- Escaping changes the characters the model sees (for example a quotation mark in a law
  name appears as `&quot;`). The quote shown to the user comes from the database.
- A citation is only checked for existing, not for supporting the claim. Whether the
  source supports the claim is measured by hand on a sample in the evaluation.
