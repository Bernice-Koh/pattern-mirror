"""Tests for the healthcheck endpoint."""

from fastapi.testclient import TestClient

from pattern_mirror import __version__


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app_env": "test", "version": __version__}


def test_health_response_carries_correlation_id(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers.get("X-Request-ID")
