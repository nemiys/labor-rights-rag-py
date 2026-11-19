# ADR-0009: When to refuse, and what is checked before an answer is shown

## Status
Accepted. The threshold of 0.5 was kept after the evaluation: on both the dev and the
test split it refused no answerable question (tables in `eval/results/`).

## Context
The search always returns something, even for a question the corpus does not cover
("דמי הבראה" returns chunks). On the vector similarity of the closest chunk, 8 questions
with an answer in the corpus scored 0.61 to 0.72; 4 off-topic questions scored 0.36 to
0.43; 2 labor-related topics that are not in the corpus scored 0.53 and 0.55. That is 14
questions written by hand for this check, in clean wording: it shows a gap, not a
threshold to trust. A wrong answer in a legal topic is worse than a refusal.

## Decision
- **Two layers.** (1) If the best vector similarity is below `MIN_VECTOR_SCORE` (a careful
  0.5 to start), refuse without calling the model: no cost. (2) Otherwise the model reads
  the sections and answers `[NO_ANSWER]` if they do not answer.
- **The score is the vector cosine similarity of the best candidate**, kept through the
  fusion. The RRF score says nothing about closeness, and the text-search score is on
  another scale for every question.
- **Every reply is checked before it is shown.** A reply that cites a source that was
  never given, or cites none, is rejected as a whole and replaced by the refusal
  sentence. The status (`answered`, `refused_low_score`, `refused_by_model`,
  `rejected_invalid_citations`, `rejected_no_citations`) is returned and logged, and the
  person sees only the answer or the sentence.
- **The refusal sentence, the disclaimer and the currency warnings are written in code.**
  The person never reads a refusal the model composed.
- **The verification card is built from the database:** the quote is the stored text of
  the section, with the law, the text date, the currency warning, the links to the
  Knesset site, the Open Law Book and the last amendment, and the disclaimer.
- **No sections are shown on a refusal.** Showing the closest sections of a question the
  corpus does not cover could mislead.

## Alternatives considered
- **Threshold only:** one number to tune; a wrong refusal hurts a real question, and the
  labor-related topics outside the corpus are close to the lowest real scores.
- **The model decides, without a threshold:** it reads the text, but costs a call for a
  hopeless question, and a free model may answer anyway.
- **Keep an answer with some invalid citation numbers, removing the markers:** more
  answers get through, but a model that invented a source is not reliable on the rest.

## Consequences
- The threshold depends on the embedding model. Changing the model needs a new check.
- A citation proves a source exists, not that it supports the claim. That is measured by
  hand on a sample in the evaluation.
