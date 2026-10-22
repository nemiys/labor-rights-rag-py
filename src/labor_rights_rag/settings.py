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


settings = Settings()
