# ADR-0005: Embedding model

## Status
Accepted for development; the measured comparison is part of the evaluation (stage 6).

## Context
The Claude API has no embeddings endpoint, so the vectors come from a local
multilingual model. The text is Hebrew, so an English-only model is out. Candidates:
BGE-M3 (1,024 dimensions, input up to about 8,000 tokens, no prefixes) and
multilingual-e5 (384 to 1,024 dimensions depending on size, input about 512 tokens,
needs the prefixes `query: ` and `passage: `). Our chunks go up to 1,500 characters
and carry a header, which is close to the e5 input limit in Hebrew. These figures come
from the model cards as I know them and are checked when the model is first loaded.

## Decision
- **Start with BGE-M3** behind an `Embedder` interface (`embed_documents`,
  `embed_query`, `name`, `dim`). No code outside `embeddings/` knows which model runs.
- **Dimension 1,024** in `chunks.embedding vector(1024)`. A model with another
  dimension needs a migration. Every chunk stores `embedding_model`.
- **Cosine distance with an HNSW index.**
- **The chunk hash covers the embedded text** (header and body), so a change in the
  header or the model recomputes the vector. Indexing computes only chunks that have
  no vector for the current model.
- **Tests use a fake embedder** (hashed words). CI never downloads the model.
- **The comparison with multilingual-e5 is done in stage 6**, on the evaluation
  questions, with hit@k and MRR for both. Both models give 1,024 dimensions at the
  large size, so the comparison needs no schema change. If e5 wins, the decision is
  replaced in a new ADR.

## Alternatives considered
- **multilingual-e5-large first:** same dimension, but the input limit and the prefix
  rule add risk (silent truncation, silent quality loss when a prefix is forgotten).
- **Compare before building:** needs evaluation questions that do not exist yet.
- **A hosted embeddings API:** adds a second vendor, a key and a cost per query for a
  corpus of about a thousand chunks.

## Consequences
- `sentence-transformers` brings `torch`: a large install, in the image too.
- The first run downloads the model (about 2 GB).
- Changing the model later re-embeds about a thousand chunks: minutes.
