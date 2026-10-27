"""Centralized configuration.

Defaults point at localhost and the host-mapped Docker ports, so a plain local
run needs no setup. Inside a container the same values are overridden through
environment variables (there "localhost" reaches nothing; the service name does).
"""

from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://labor:labor@localhost:5435/labor"

    # Which embedding model computes vectors: "bge-m3" (needs the extra) or "hash" (a fake).
    embedder: str = "bge-m3"

    # Hybrid search (ADR-0007): the RRF constant, and how many candidates each search gives.
    rrf_k: int = 10  # 60 was the first value; 10 was better on the dev questions (ADR-0010)
    search_candidates: int = 50

    # Refuse without calling the model when even the closest chunk is further than this
    # (cosine similarity, BGE-M3). A first, careful value; tuned in the evaluation.
    min_vector_score: float = 0.5
    # Which model writes the answers: "fake" (tests), "claude", or "chat" (any model that
    # speaks the /chat/completions protocol: Ollama, a free hosted service).
    answerer: str = "fake"
    anthropic_api_key: SecretStr | None = None
    answer_model: str = "claude-sonnet-5-5"
    answer_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    chat_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    chat_model: str = ""
    chat_api_key: SecretStr | None = None

    # Use the HNSW index for the vector search. Off: an exact scan, which is right for about a
    # thousand vectors (docs/adr/0011).
    vector_index: bool = False

    corpus_path: str = "corpus.toml"
    knesset_odata_url: str = "https://knesset.gov.il/OdataV4/ParliamentInfo"
    wikisource_api_url: str = "https://he.wikisource.org/w/api.php"
    # Wikimedia asks API clients to identify themselves with a way to reach the owner.
    http_user_agent: str = "labor-rights-rag/0.1 (portfolio project; nemiys@gmail.com)"
    request_delay_seconds: float = 1.0


settings = Settings()
