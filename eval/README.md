# The evaluation questions

`questions.jsonl` has 56 questions about Israeli labor law, written from the point of view
of a person with no legal background. They were written by the assistant and are approved by
the project owner. **The file is frozen**: its SHA-256 is in `QUESTIONS.sha256`, and a test
fails if the file changes. A change must be deliberate: edit the file, update the hash, and
say why in the commit.

## Fields

| Field | Meaning |
|---|---|
| `id` | `p` everyday wording, `e` exact term, `m` several sections, `w` words differ from the law, `u` unanswerable |
| `split` | `dev`: used to tune settings. `test`: run once, at the end |
| `answerable` | whether the corpus answers it |
| `expected` | the law (Knesset id) and section that answer it; empty when not answerable |
| `expected_facts` | groups of phrasings; a fact counts when any phrasing is in the answer |
| `notes` | a caveat about the ground truth |

## Mix

| Type | Questions | What it tests |
|---|---|---|
| everyday wording | 20 | meaning, with none of the law's words |
| exact terms and numbers | 10 | what word search is for |
| several sections | 10 | an answer that needs more than one section |
| words differ | 6 | a question phrased differently from the law (claim / limitation period) |
| unanswerable | 10 | refusal, including topics that are mentioned but not granted (recovery pay) |

## How it was written, against bias

1. Each question is in a citizen's words, not copied from a section.
2. Each expected section was read in the real text before any search result was looked at,
   and every fact is checked by a script to be in the expected sections.
3. The unanswerable questions were checked: the topic is not in the corpus as an entitlement.
   Where the words appear (for example recovery pay), a note says where.
4. The set was written once and frozen. No question was removed or reworded because of how
   the system answered. The author knew of one weakness before writing (the limitation
   period question, `w01`), and it is one of six questions of its kind.
5. `dev` (39) is for tuning the threshold, `k` and the chunk size. `test` (17) is run once.

## Limits

The ground truth is one reader's judgment of which sections answer a question. Where two
sections could answer it, both are listed and a hit on either counts. A citation shows that
the section exists, not that it supports the claim: that is checked by hand on a sample.
