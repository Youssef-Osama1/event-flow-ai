from functools import lru_cache
from pathlib import Path

from typing import Any

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "event-flow-ai"
    log_level: str = "INFO"
    api_key: SecretStr | None = None

    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "postgres"
    database_user: str = "postgres"
    database_password: SecretStr = SecretStr("postgres")
    database_url_override: str | None = None

    redis_url: str = "redis://localhost:6379/0"

    default_model_name: str = "openai/gpt-oss-120b"
    groq_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: SecretStr | None = None
    azure_openai_api_version: str = "2025-04-01-preview"
    ollama_base_url: str = "http://localhost:11434/v1"

    enable_tracing: bool = False
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"

    @field_validator(
        "api_key",
        "groq_api_key",
        "openai_api_key",
        "anthropic_api_key",
        "google_api_key",
        "azure_openai_api_key",
        "azure_openai_endpoint",
        "langfuse_public_key",
        "langfuse_secret_key",
        "database_url_override",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        password = self.database_password.get_secret_value()
        return (
            f"postgresql+psycopg://{self.database_user}:{password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
