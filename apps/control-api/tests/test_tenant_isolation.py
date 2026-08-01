"""Tenant isolation for durable decisions and approvals."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.decision_store import DecisionStore, reset_decision_store
from app.settings import clear_settings_cache


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DecisionStore:
    db_path = tmp_path / "tenant.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TENANT_ISOLATION", "true")
    clear_settings_cache()
    reset_decision_store(None)
    instance = DecisionStore.from_env()
    reset_decision_store(instance)
    yield instance
    reset_decision_store(None)
    instance.close()
    clear_settings_cache()


def test_store_filters_decisions_by_tenant(store: DecisionStore) -> None:
    a = store.create_decision(
        final_verdict="allow", team="platform", tenant_id="platform"
    )
    b = store.create_decision(
        final_verdict="allow", team="finance", tenant_id="finance"
    )
    assert store.get_decision(a, tenant_id="platform") is not None
    assert store.get_decision(a, tenant_id="finance") is None
    assert store.get_decision(b, tenant_id="finance") is not None


def test_api_hides_cross_tenant_decision(
    store: DecisionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TENANT_ISOLATION", "true")
    clear_settings_cache()
    decision_id = store.create_decision(
        final_verdict="allow", team="platform", tenant_id="platform"
    )
    from app.main import app

    client = TestClient(app)
    missing = client.get(
        f"/governance/decisions/{decision_id}",
        headers={"x-ai-tenant": "finance"},
    )
    assert missing.status_code == 404
    ok = client.get(
        f"/governance/decisions/{decision_id}",
        headers={"x-ai-tenant": "platform"},
    )
    assert ok.status_code == 200
    assert ok.json()["tenant_id"] == "platform"
