# docs-assistant-py

Question answering over the FastAPI documentation: crawl, chunk, embed, hybrid
retrieval (vector + full-text), and answers with citations.

Retrieval is written by hand (no LangChain / LlamaIndex) and measured with
hit@k and MRR on a hand-written question set.

> Status: stage 0 (project skeleton). Nothing but `/health` works yet.

## Run locally

```
docker compose up -d --wait
uv sync
uv run pytest
uv run uvicorn docs_assistant.main:app --port 8002
```

The app is also available through Compose on `http://localhost:8002/health`.

Ports: Postgres 5435, Redis 6382, app 8002.

## Decisions

Architecture decision records live in [docs/adr/](docs/adr/).
