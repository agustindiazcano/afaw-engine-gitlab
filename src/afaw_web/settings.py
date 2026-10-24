"""Service settings, read from environment variables prefixed AFAW_WEB_."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Where the baked-in data lives: live/ (derived views), demo/, docs/adr and docs/gotchas."""

    model_config = SettingsConfigDict(env_prefix="AFAW_WEB_")

    data_dir: Path = Path("/app/data")
