"""Tests for the health check endpoint."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200() -> None:
    """The /api/health endpoint should respond with HTTP 200."""
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_returns_expected_payload() -> None:
    """The /api/health endpoint should report status 'ok' with app metadata."""
    response = client.get("/api/health")
    body = response.json()

    assert body["status"] == "ok"
    assert "app_name" in body
    assert "version" in body
    assert "environment" in body
