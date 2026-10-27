FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# The virtual environment is put on PATH, so nothing needs `uv run` at runtime.
# HF_HOME is where the embedding model is downloaded; Compose mounts a volume there.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    PATH="/app/.venv/bin:$PATH"

# The application does not run as root.
RUN useradd --create-home app && mkdir /models && chown app /models

WORKDIR /app

# Dependencies first: this layer is cached until pyproject.toml / uv.lock change.
# The embeddings extra is part of the image: the application loads BGE-M3 at startup.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --extra embeddings

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini corpus.toml ./
RUN uv sync --frozen --no-dev --extra embeddings

USER app

CMD ["uvicorn", "labor_rights_rag.main:app", "--host", "0.0.0.0", "--port", "8000"]
