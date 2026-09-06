from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    service_name: str = "agentic-doc-intel"
    database_url: str = "sqlite+aiosqlite:///./docintel.db"
    mongo_url: str = "mongodb://localhost:27017"
    mongo_database: str = "docintel"
    redis_url: str = "redis://localhost:6379/0"
    demo_api_key: str = ""
    admin_api_key: str = ""

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-06-01"
    azure_openai_chat_deployment: str = "gpt-4o"
    azure_openai_embedding_deployment: str = "text-embedding-3-large"

    vector_backend: Literal["postgres", "pgvector", "azure_ai_search", "memory"] = "memory"
    embedding_dimensions: int = 3072
    upload_dir: Path = Field(default=Path("/tmp/docintel_uploads"))
    chunk_size: int = 1200
    chunk_overlap: int = 180
    retrieval_top_k: int = 8
    otel_exporter_otlp_endpoint: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
