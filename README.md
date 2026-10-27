# labor-rights-rag-py

Question answering over Israeli labor laws, in Hebrew: fetch, parse, chunk,
embed, hybrid retrieval (vector + full-text), and answers with citations and a
verification card that points to the official Knesset legislation database.

Retrieval is written by hand (no LangChain / LlamaIndex) and measured with
hit@k and MRR on a hand-written question set, against two baselines (no
retrieval, and all laws in the prompt).

> Status: stage 1 (decisions and data model). Nothing but `/health` works yet.
> Not legal advice. The binding text of a law is published in Reshumot.

## Run locally

```
docker compose up -d --wait
uv sync
uv run pytest
uv run uvicorn labor_rights_rag.main:app --port 8002
```

The app is also available through Compose on `http://localhost:8002/health`.

Ports: Postgres 5435, app 8002.

## Decisions

Architecture decision records live in [docs/adr/](docs/adr/).
