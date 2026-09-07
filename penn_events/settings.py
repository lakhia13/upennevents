"""Runtime settings, read from the environment (see .env.example)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://penn:penn@localhost:5432/pennevents",
        alias="DATABASE_URL",
    )
    config_path: str | None = Field(default=None, alias="PENN_CONFIG_PATH")
    tag_rules_path: str | None = Field(default=None, alias="PENN_TAG_RULES_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    display_timezone: str = Field(default="America/New_York", alias="DISPLAY_TIMEZONE")
    max_concurrent_feeders: int = Field(default=8, alias="MAX_CONCURRENT_FEEDERS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
