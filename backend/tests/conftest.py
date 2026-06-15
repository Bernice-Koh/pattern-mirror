"""Shared fixtures for the backend test suite."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from pattern_mirror.core.config import get_settings
from pattern_mirror.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A TestClient over a freshly built app pinned to the test environment.

    The ``with`` block drives the app's lifespan (startup/shutdown), and the
    settings cache is reset so the app picks up the patched environment.
    """
    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()
