# labor-rights-rag-py

Question answering over Israeli labor laws, in Hebrew: fetch, parse, chunk,
embed, hybrid retrieval (vector + full-text), and answers with citations and a
verification card that points to the official Knesset legislation database.

Retrieval is written by hand (no LangChain / LlamaIndex) and measured with
hit@k and MRR on a hand-written question set, against two baselines (no
retrieval, and all laws in the prompt).

> Status: stage 1 (decisions and data model). Nothing but `/health` works yet.
> Not legal advice. The binding text of a law is published in Reshumot.

## Run with Docker

```
docker compose up -d --wait        # Postgres, migrations, the application
docker compose run --rm ingest     # once: fetch the 20 laws and index them
```

Then open `http://localhost:8002`. The first start downloads the embedding model
(BGE-M3, about 2 GB) into a volume, so later starts are fast. The first `ingest` embeds
about 900 chunks on the CPU and takes around half an hour; running it again changes
nothing unless a law changed.

Answers are fake until a model is configured. Copy `.env.example` to `.env` and set
`ANSWERER` (see the comments there); Compose reads it at run time and never copies it
into the image.

## Run locally

```
docker compose up -d --wait postgres
uv sync --extra embeddings
uv run alembic upgrade head
uv run pytest
uv run uvicorn labor_rights_rag.main:app --port 8002
```

Ports: Postgres 5435, app 8002.

## Decisions

Architecture decision records live in [docs/adr/](docs/adr/).
