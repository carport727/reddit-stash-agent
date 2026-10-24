from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api import server

AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture()
def client():
    with TestClient(server.app) as test_client:
        yield test_client


def test_health_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["auth_required"] is True


def test_token_required(client):
    assert client.get("/api/status").status_code == 401
    assert client.get("/api/status", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/api/sync").status_code == 401
    assert client.get("/api/status", headers=AUTH).status_code == 200


def test_config_push_does_not_postpone_next_run(client):
    body = {"enabled": True, "interval_hours": 6}
    first = client.put("/api/config", json=body, headers=AUTH).json()
    assert first["next_run_at"]

    for _ in range(3):
        client.get("/api/status", headers=AUTH)
        again = client.put("/api/config", json=body, headers=AUTH).json()
    assert again["next_run_at"] == first["next_run_at"]

    changed = client.put("/api/config", json={"enabled": True, "interval_hours": 2}, headers=AUTH).json()
    assert changed["interval_hours"] == 2.0

    off = client.put("/api/config", json={"enabled": False, "interval_hours": 2}, headers=AUTH).json()
    assert off["next_run_at"] is None


def test_invalid_interval_rejected(client):
    response = client.put("/api/config", json={"enabled": True, "interval_hours": 0}, headers=AUTH)
    assert response.status_code == 422


def test_cancel_without_sync(client):
    assert client.post("/api/sync/cancel", headers=AUTH).status_code == 409


def test_compute_next_run():
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    interval = timedelta(hours=6)

    assert server.compute_next_run(interval, None, now) == now + server.FIRST_RUN_DELAY
    assert server.compute_next_run(interval, now - timedelta(hours=1), now) == now + timedelta(hours=5)
    assert server.compute_next_run(interval, now - timedelta(days=2), now) == now + server.OVERDUE_RUN_DELAY
