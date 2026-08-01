"""Liveness / readiness probe contract."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main
from app.decision_store import StoreUnavailableError

client = TestClient(app_main.app)


def test_livez_ok() -> None:
    response = client.get("/livez")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readyz_ok_when_store_available() -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["store_ok"] is True
    assert payload["policy_bundle_ok"] is True


def test_readyz_503_when_store_ping_fails(monkeypatch) -> None:
    class _DeadStore:
        def ping(self) -> bool:
            return False

    monkeypatch.setattr(
        "app.routers.health.get_decision_store",
        lambda: _DeadStore(),
    )
    response = client.get("/readyz")
    assert response.status_code == 503


def test_readyz_503_when_store_unavailable(monkeypatch) -> None:
    def _boom():
        raise StoreUnavailableError("authoritative store unavailable")

    monkeypatch.setattr("app.routers.health.get_decision_store", _boom)
    response = client.get("/readyz")
    assert response.status_code == 503


def test_health_reports_ready_flags() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["live"] is True
    assert "store_ok" in payload
    assert "ready" in payload
