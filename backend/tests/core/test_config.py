"""Tests for typed settings loading and fail-loud validation."""

import pytest
from pydantic import ValidationError

from pattern_mirror.core.config import _REPO_ROOT, Settings

# Settings are constructed with _env_file=None so the suite never reads the
# developer's real .env at the repo root; every value comes from the patched
# process environment, keeping each test hermetic.


def test_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    settings = Settings(_env_file=None)

    assert settings.app_env == "production"
    assert settings.log_level == "WARNING"


def test_log_level_defaults_to_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.log_level == "INFO"


def test_missing_required_variable_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert "app_env" in str(exc_info.value).lower()


def test_repo_root_anchor_points_at_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    # Guards the parents[4] depth in config.py: if the file ever moves, this
    # fails loudly instead of silently resolving .env to the wrong directory.
    assert (_REPO_ROOT / ".env.example").is_file()
