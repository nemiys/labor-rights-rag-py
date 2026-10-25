"""Centralized configuration.

Defaults point at localhost and the host-mapped Docker ports, so a plain local
run needs no setup. Inside a container the same values are overridden through
environment variables (there "localhost" reaches nothing; the service name does).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://docs:docs@localhost:5435/docs"
    redis_url: str = "redis://localhost:6382/0"

    # Which embedding model computes vectors: "bge-m3" (needs the extra) or "hash" (a fake).
    embedder: str = "bge-m3"

    # Hybrid search (ADR-0007): the RRF constant, and how many candidates each search gives.
    rrf_k: int = 60
    search_candidates: int = 50

    # Refuse without calling the model when even the closest chunk is further than this
    # (cosine similarity, BGE-M3). A first, careful value; tuned in the evaluation.
    min_vector_score: float = 0.5
    # Which model writes the answers: "fake" until the real ones are connected.
    answerer: str = "fake"

    corpus_path: str = "corpus.toml"
    knesset_odata_url: str = "https://knesset.gov.il/OdataV4/ParliamentInfo"
    wikisource_api_url: str = "https://he.wikisource.org/w/api.php"
    # Wikimedia asks API clients to identify themselves with a way to reach the owner.
    http_user_agent: str = "labor-rights-rag/0.1 (portfolio project; nemiys@gmail.com)"
    request_delay_seconds: float = 1.0


settings = Settings()
