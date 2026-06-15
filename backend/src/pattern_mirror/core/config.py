"""Typed application settings sourced from the environment and a local ``.env``.

Settings are validated when first loaded (at process startup), so a missing or
malformed variable aborts boot loudly with a message naming the offending
field, rather than failing deep inside a later request.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root (where .env lives) is four levels up from this file.
_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Runtime configuration for the backend service.

    Only the variables the current skeleton actually consumes are modelled here;
    database, LLM, and blob-storage settings are added by the issues that
    introduce the code using them. Unrelated variables in ``.env`` are ignored.
    """

    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return the application settings, loading and validating them once.

    The result is cached so every caller shares a single validated instance and
    the environment is read only once. Tests can reset the cache with
    ``get_settings.cache_clear()``.
    """
    return Settings()
