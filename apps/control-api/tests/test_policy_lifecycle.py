"""Policy bundle validate / simulate / activate / rollback."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.decision_store import DecisionStore, reset_decision_store
from app.governance_service import get_governance_root
from app.policy_bundle import clear_policy_bundle, get_policy_bundle
from app.policy_lifecycle import reset_policy_lifecycle
from app.settings import clear_settings_cache


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "policy.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    clear_settings_cache()
    clear_policy_bundle()
    reset_policy_lifecycle()
    reset_decision_store(None)
    store = DecisionStore.from_env()
    reset_decision_store(store)
    from app.main import app

    client = TestClient(app)
    yield client, store
    reset_decision_store(None)
    store.close()
    clear_policy_bundle()
    reset_policy_lifecycle()
    clear_settings_cache()


def test_validate_simulate_activate_rollback(api) -> None:
    client, store = api
    root = str(get_governance_root())

    validated = client.post(
        "/governance/policy-bundles/validate",
        json={"type": "filesystem", "path": root},
    )
    assert validated.status_code == 200, validated.text
    bundle_id = validated.json()["bundle"]["bundle_id"]
    assert bundle_id

    # Seed historical decisions for impact simulation.
    store.create_decision(
        final_verdict="allow",
        team="platform",
        tenant_id="platform",
        model="llama3.1:8b",
        request={
            "team": "platform",
            "owner": "alice",
            "environment": "development",
            "namespace": "ai-dev",
            "action": "invoke_model",
            "model": "llama3.1:8b",
            "provider": "ollama",
        },
    )
    store.create_decision(
        final_verdict="block",
        team="platform",
        tenant_id="platform",
        model="unknown-model",
        request={
            "team": "platform",
            "owner": "alice",
            "environment": "production",
            "namespace": "ai-prod",
            "action": "invoke_model",
            "model": "unknown-model",
            "provider": "ollama",
            "policy_pack": "production",
        },
    )

    simulated = client.post(
        f"/governance/policy-bundles/{bundle_id}/simulate?limit=50"
    )
    assert simulated.status_code == 200, simulated.text
    body = simulated.json()
    assert body["evaluated_decisions"] >= 1
    assert "unchanged" in body

    impact = client.get(f"/governance/policy-bundles/{bundle_id}/impact")
    assert impact.status_code == 200
    assert impact.json()["bundle_id"] == bundle_id

    active_before = get_policy_bundle().bundle_id
    activated = client.post(f"/governance/policy-bundles/{bundle_id}/activate")
    assert activated.status_code == 200
    assert get_policy_bundle().bundle_id == bundle_id

    # Second validate+activate creates a rollback point.
    validated2 = client.post(
        "/governance/policy-bundles/validate",
        json={"type": "filesystem", "path": root},
    )
    assert validated2.status_code == 200
    bid2 = validated2.json()["bundle"]["bundle_id"]
    client.post(f"/governance/policy-bundles/{bid2}/activate")
    rolled = client.post("/governance/policy-bundles/rollback")
    assert rolled.status_code == 200
    assert rolled.json()["bundle_id"]

    listed = client.get("/governance/policy-bundles")
    assert listed.status_code == 200
    roles = {item["role"] for item in listed.json()}
    assert "active" in roles
    assert active_before  # sanity
