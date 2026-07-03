"""Typed application settings sourced from the environment and a local ``.env``.

Settings are validated when first loaded (at process startup), so a missing or
malformed variable aborts boot loudly with a message naming the offending
field, rather than failing deep inside a later request.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from pattern_mirror.models.enums import BiasCategory


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

    # HMAC key for signing mock session tokens. The default keeps tests and local
    # boot working without extra env plumbing; production overrides it. This is mock
    # auth, not real security, so a shipped default is acceptable.
    session_secret: str = "dev-only-mock-session-key-override-in-production"

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
    # engine (design spec: Sonnet 4.6 for these stages).
    analysis_model: str = "claude-sonnet-4-6"

    # The Judge Agent's model (design spec: Haiku 4.5 for confidence scoring).
    judge_model: str = "claude-haiku-4-5"

    # Per-agent models for the four-agent dictionary-growth review (ADR 0012). The
    # argument- and citation-recall roles run on Sonnet; the scope classification is a
    # narrow call that Haiku handles. Kept in config so the tiering is tunable per ADR.
    growth_proposer_model: str = "claude-sonnet-4-6"
    growth_skeptic_model: str = "claude-sonnet-4-6"
    growth_categorizer_model: str = "claude-haiku-4-5"
    growth_citation_model: str = "claude-sonnet-4-6"

    # The Judge's gate, on the calibrated score (>= passes, ADR-0008). In config so it
    # is tunable per environment without a code change; a flag whose calibrated confidence
    # falls below it is logged but not surfaced and gets no recommendation.
    judge_confidence_threshold: float = 0.7

    # Per-category threshold overrides (ADR-0008): category -> threshold. Categories absent
    # here fall back to ``judge_confidence_threshold``.
    judge_confidence_threshold_overrides: dict[BiasCategory, float] = {}

    # The Pattern Aggregator's significance gate (#66): a pattern surfaces only if its Fisher's
    # exact p-value is strictly below this. In config so the bar is tunable without a code change.
    pattern_significance_threshold: float = 0.05

    # Minimum distinct managers an HR aggregate cell must cover (#70, §11): cells below this are
    # suppressed so no firm-level figure can re-identify an individual manager.
    hr_min_cell_size: int = 3

    # The Dictionary Growth trigger's recurrence floor (#88): a general, uncatalogued phrase
    # surfaces as a growth candidate once the Contextual Pass has proposed it across at least this
    # many distinct documents (and managers). The trigger's job is only cheap fluke rejection —
    # since each phrase is reviewed once, a floor of two documents keeps that one review off n=1
    # evidence. Generality is the Categorizer's call (#89), not a cross-manager count, so the
    # manager axis defaults to 1; both knobs stay so production can raise the bar as volume grows.
    growth_recurrence_min_managers: int = 1
    growth_recurrence_min_documents: int = 2

    # Root of the local-disk blob stand-in (#118). Resume/CV files are the only binary artefacts
    # (design spec §5); dev writes them under this folder, production swaps in an Azure Blob store
    # behind the same interface. Kept as a plain path string so the value maps straight to a
    # filesystem root without model coupling.
    blob_storage_path: str = "./deploy/blob-data"


@lru_cache
def get_settings() -> Settings:
    """Return the application settings, loading and validating them once.

    The result is cached so every caller shares a single validated instance and
    the environment is read only once. Tests can reset the cache with
    ``get_settings.cache_clear()``.
    """
    return Settings()
