"""Typed application settings sourced from the environment and a local ``.env``.

Settings are validated when first loaded (at process startup), so a missing or
malformed variable aborts boot loudly with a message naming the offending
field, rather than failing deep inside a later request.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the backend service.

    Only the variables the current skeleton actually consumes are modelled here;
    database, LLM, and blob-storage settings are added by the issues that
    introduce the code using them. Unrelated variables in ``.env`` are ignored.
    """

    model_config = SettingsConfigDict(
        # Loaded from a .env in the working directory (backend/) in dev; in CI
        # and prod no .env ships and real environment variables are used.
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # SQLAlchemy URL for the development/production database, e.g.
    # postgresql+psycopg://user:pass@host:5432/pattern_mirror. Kept as a string
    # rather than PostgresDsn so the psycopg driver suffix passes through to
    # create_engine untouched.
    database_url: str

    # The test suite targets this database so it never collides with dev data.
    # Unset in CI, where database_url already points at a disposable container;
    # the suite falls back to database_url in that case.
    test_database_url: str | None = None

    # Anthropic API key for the LLM Agent stages (Contextual Pass, Judge,
    # Recommendations). Optional so the service and the test suite boot without
    # it — tests mock every Anthropic call; the Agent nodes raise only if invoked
    # without a key. Never logged or committed.
    anthropic_api_key: str | None = None

    # Model for the analysis Agents (the Contextual Pass; later Recommendations).
    # Kept in config, not hard-coded, so it can be swapped without touching the
    # engine (design spec: Sonnet 4.6 for these stages). The Judge model and the
    # confidence threshold land with the Judge stage (#49) that consumes them.
    analysis_model: str = "claude-sonnet-4-6"


@lru_cache
def get_settings() -> Settings:
    """Return the application settings, loading and validating them once.

    The result is cached so every caller shares a single validated instance and
    the environment is read only once. Tests can reset the cache with
    ``get_settings.cache_clear()``.
    """
    return Settings()
