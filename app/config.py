from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROVIDERS_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "providers.yaml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str
    celery_broker_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None
    together_api_key: str | None = None
    fireworks_api_key: str | None = None
    hf_token: str | None = None
    hf_model: str = "Qwen/Qwen3-4B-Instruct-2507:nscale"
    hf_verify_model: str = "meta-llama/Llama-3.1-8B-Instruct:nscale"
    ollama_base_url: str = "http://localhost:11434/v1"
    # Two distinct models so generation and verification are genuinely
    # independent calls even when Ollama is the only working provider —
    # see app/providers/llm/ollama_provider.py.
    ollama_model: str = "llama3.3"
    ollama_verify_model: str = "llama3.3"
    embedding_provider_api_key: str | None = None
    ocr_fallback_api_key: str | None = None

    @field_validator("database_url")
    @classmethod
    def use_async_postgres_driver(cls, value: str) -> str:
        """Accept managed Postgres URLs with asyncpg-compatible TLS options."""
        parsed = urlsplit(value)
        if parsed.scheme not in {"postgres", "postgresql", "postgresql+asyncpg"}:
            return value
        query = []
        for key, setting in parse_qsl(parsed.query, keep_blank_values=True):
            if key == "sslmode":
                query.append(("ssl", setting))
            elif key != "channel_binding":
                query.append((key, setting))
        return urlunsplit(("postgresql+asyncpg", parsed.netloc, parsed.path,
                           urlencode(query), parsed.fragment))


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # pydantic-settings loads from env


@lru_cache
def get_provider_config() -> dict[str, Any]:
    with PROVIDERS_CONFIG_PATH.open() as f:
        return yaml.safe_load(f)  # type: ignore[no-any-return]
