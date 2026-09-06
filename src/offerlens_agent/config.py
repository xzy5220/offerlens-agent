"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings shared by the graph, API, and evaluation harness."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OFFERLENS_",
        extra="ignore",
        case_sensitive=False,
    )

    mode: Literal["demo", "live"] = "demo"
    model: str = "openai:gpt-4.1-mini"
    search_provider: Literal["fixture", "tavily", "duckduckgo"] = "fixture"
    checkpoint_backend: Literal["memory", "sqlite"] = "sqlite"
    max_revisions: int = Field(default=2, ge=0, le=5)
    require_approval: bool = False
    max_resume_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    max_job_description_chars: int = Field(default=50_000, ge=1000)
    data_dir: Path = Path(".offerlens")
    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("data_dir", mode="after")
    @classmethod
    def normalize_data_dir(cls, value: Path) -> Path:
        """Keep filesystem handling consistent across the API and CLI."""
        return value.expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
