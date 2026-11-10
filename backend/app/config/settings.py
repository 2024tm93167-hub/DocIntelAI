"""Application configuration loaded from environment variables (.env)."""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "DocIntel AI"
    environment: Literal["development", "production", "test"] = "development"

    # Firebase Admin SDK
    firebase_service_account_path: str = "serviceAccountKey.json"
    firebase_service_account_json: str | None = None
    firebase_project_id: str | None = None

    # CORS
    cors_origins: str = "http://localhost:4200"

    # AI provider selection ("openai" or "ollama")
    ai_provider: Literal["openai", "ollama"] = "ollama"

    # OpenAI-compatible provider
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # Ollama provider
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    ai_timeout_seconds: float = 30.0
    ai_temperature: float = 0.4

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
