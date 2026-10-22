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

    corpus_path: str = "corpus.toml"
    knesset_odata_url: str = "https://knesset.gov.il/OdataV4/ParliamentInfo"
    wikisource_api_url: str = "https://he.wikisource.org/w/api.php"
    # Wikimedia asks API clients to identify themselves with a way to reach the owner.
    http_user_agent: str = "labor-rights-rag/0.1 (portfolio project; nemiys@gmail.com)"
    request_delay_seconds: float = 1.0


settings = Settings()
