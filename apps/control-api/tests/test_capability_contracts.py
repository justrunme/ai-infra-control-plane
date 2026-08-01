"""Durable agent/tool capability contracts."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.capability_service import sync_from_filesystem
from app.decision_store import DecisionStore, reset_decision_store
from app.main import app
from app.settings import clear_settings_cache


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DecisionStore:
    db_url = f"sqlite:///{tmp_path / 'capabilities.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    clear_settings_cache()
    reset_decision_store(None)
    decision_store = DecisionStore(db_url)
    reset_decision_store(decision_store)
    yield decision_store
    reset_decision_store(None)
    clear_settings_cache()


def test_sync_and_activate_capability_contracts(store: DecisionStore) -> None:
    synced = sync_from_filesystem(tenant_id="platform", activate=True, store=store)
    assert synced
    kinds = {item.kind for item in synced}
    assert "agent" in kinds
    assert "tool" in kinds
    assert all(item.status == "active" for item in synced)
    assert "008_capability_contracts" in store.list_schema_migrations()

    page = store.list_capability_contracts(status="active", limit=500)
    assert page.total >= 1
    # Re-sync same content is idempotent by digest.
    again = sync_from_filesystem(tenant_id="platform", activate=True, store=store)
    assert len(again) == len(synced)


def test_capability_api_sync_list_retire(
    store: DecisionStore,
) -> None:
    client = TestClient(app)
    synced = client.post(
        "/registry/capabilities/sync",
        json={"tenant_id": "platform", "activate": True},
    )
    assert synced.status_code == 200, synced.text
    body = synced.json()
    assert body["synced"] >= 1

    listed = client.get("/registry/capabilities", params={"status": "active"})
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    active_tools = client.get("/registry/capabilities/active/tool")
    assert active_tools.status_code == 200
    assert isinstance(active_tools.json(), list)

    contract_id = body["contracts"][0]["contract_id"]
    got = client.get(f"/registry/capabilities/{contract_id}")
    assert got.status_code == 200
    assert got.json()["content_digest"].startswith("sha256:")

    retired = client.post(f"/registry/capabilities/{contract_id}/retire")
    assert retired.status_code == 200
    assert retired.json()["status"] == "retired"

    # Re-activate after retire for lifecycle coverage.
    activated = client.post(f"/registry/capabilities/{contract_id}/activate")
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"
    missing = client.get("/registry/capabilities/does-not-exist")
    assert missing.status_code == 404
