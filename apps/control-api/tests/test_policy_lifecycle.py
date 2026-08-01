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

    active_record = store.get_active_policy_bundle()
    assert active_record is not None
    assert active_record.generation is not None
    assert active_record.generation >= 1


def test_ha_replica_catches_up_active_generation(tmp_path: Path, monkeypatch) -> None:
    """Two PolicyLifecycle instances share one store and catch up by generation."""
    from app.policy_lifecycle import PolicyLifecycle

    db_path = tmp_path / "ha-policy.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    clear_settings_cache()
    clear_policy_bundle()
    reset_policy_lifecycle()
    reset_decision_store(None)

    store = DecisionStore.from_env()
    reset_decision_store(store)
    root = get_governance_root()

    replica_a = PolicyLifecycle(store=store)
    replica_a.ensure_bootstrapped()
    validated = replica_a.validate_from_path(root)
    assert validated.validation_status == "ok"
    activated = replica_a.activate(validated.bundle_id)
    assert activated.bundle_id == validated.bundle_id
    gen = store.get_active_policy_generation()
    assert gen >= 1
    status_a = replica_a.bootstrap_status()
    assert status_a["policy_observed_generation"] == gen

    # Fresh process-local cache on replica B (shared durable store).
    clear_policy_bundle()
    replica_b = PolicyLifecycle(store=store)
    # Seed with env bootstrap path first (as a new pod would), then sync.
    replica_b.ensure_bootstrapped()
    synced = replica_b.sync_active_from_store(force=True)
    assert synced is not None
    assert synced.content_digest == activated.content_digest
    status_b = replica_b.bootstrap_status()
    assert status_b["policy_observed_generation"] == gen
    assert status_b["policy_active_generation"] == gen

    ready = TestClient(__import__("app.main", fromlist=["app"]).app).get("/readyz")
    assert ready.status_code == 200
    body = ready.json()
    assert body["policy_active_generation"] >= 1
    assert body["policy_observed_generation"] >= 1

    reset_decision_store(None)
    store.close()
    clear_policy_bundle()
    reset_policy_lifecycle()
    clear_settings_cache()
