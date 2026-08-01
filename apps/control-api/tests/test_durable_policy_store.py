"""Durable PolicyBundle store + HA generation catch-up."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.decision_store import DecisionStore, reset_decision_store
from app.governance_service import get_governance_root
from app.policy_bundle import clear_policy_bundle, get_policy_bundle
from app.policy_lifecycle import PolicyLifecycle, reset_policy_lifecycle
from app.settings import clear_settings_cache


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "durable-policy.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    clear_settings_cache()
    clear_policy_bundle()
    reset_policy_lifecycle()
    reset_decision_store(None)
    decision_store = DecisionStore.from_env()
    reset_decision_store(decision_store)
    yield decision_store
    reset_decision_store(None)
    decision_store.close()
    clear_policy_bundle()
    reset_policy_lifecycle()
    clear_settings_cache()


def test_migration_009_present(store: DecisionStore) -> None:
    assert "009_policy_bundles" in store.list_schema_migrations()


def test_upsert_activate_rollback_generation(store: DecisionStore) -> None:
    root = get_governance_root()
    life = PolicyLifecycle(store=store)
    first = life.ensure_bootstrapped()
    assert first.validation_status == "ok"
    active = store.get_active_policy_bundle()
    assert active is not None
    assert (active.generation or 0) >= 1
    gen1 = store.get_active_policy_generation()

    # Persist a second logical previous by cloning source under a temp path
    # is unnecessary: force a previous via direct status swap after upsert.
    alt = store.upsert_policy_bundle_candidate(
        bundle_id="alt-bundle",
        content_digest="deadbeef" * 8,
        git_revision="test",
        source_type="filesystem",
        source_json={"type": "filesystem", "path": str(root)},
        validation_status="ok",
        loaded_at=first.loaded_at,
    )
    assert alt.status == "candidate"
    store.activate_policy_bundle("alt-bundle", content_digest=alt.content_digest)
    assert store.get_active_policy_generation() > gen1
    previous = store.get_previous_policy_bundle()
    assert previous is not None
    assert previous.bundle_id == first.bundle_id

    rolled = store.rollback_policy_bundle()
    assert rolled.bundle_id == first.bundle_id
    assert store.get_active_policy_generation() > gen1


def test_save_and_get_impact(store: DecisionStore) -> None:
    store.save_policy_bundle_impact(
        bundle_id="b1",
        content_digest="d1",
        evaluated_decisions=10,
        unchanged=8,
        allow_to_block=1,
        allow_to_approval=1,
        block_to_allow=0,
        approval_to_allow=0,
        approval_to_block=0,
        other_changes=0,
        sample_changes=[{"decision_id": "x"}],
        simulate_limit=50,
    )
    impact = store.get_policy_bundle_impact("b1")
    assert impact is not None
    assert impact.evaluated_decisions == 10
    assert impact.sample_changes[0]["decision_id"] == "x"
    assert store.get_policy_bundle_impact("missing") is None


def test_get_policy_bundle_record_prefers_active(store: DecisionStore) -> None:
    root = str(get_governance_root())
    store.upsert_policy_bundle_candidate(
        bundle_id="same",
        content_digest="aaa",
        source_json={"type": "filesystem", "path": root},
    )
    store.upsert_policy_bundle_candidate(
        bundle_id="same",
        content_digest="bbb",
        source_json={"type": "filesystem", "path": root},
    )
    store.activate_policy_bundle("same", content_digest="bbb")
    record = store.get_policy_bundle_record("same")
    assert record is not None
    assert record.content_digest == "bbb"
    assert record.status == "active"
    listed = store.list_policy_bundle_candidates()
    assert any(item.content_digest == "aaa" for item in listed)


def test_replica_sync_and_evaluate_path(store: DecisionStore) -> None:
    root = get_governance_root()
    a = PolicyLifecycle(store=store)
    a.ensure_bootstrapped()
    candidate = a.validate_from_path(root)
    a.activate(candidate.bundle_id)
    digest = candidate.content_digest
    gen = store.get_active_policy_generation()

    clear_policy_bundle()
    b = PolicyLifecycle(store=store)
    assert b.bootstrap_status()["policy_observed_generation"] == 0
    synced = b.sync_active_from_store(force=True)
    assert synced is not None
    assert synced.content_digest == digest
    assert b.bootstrap_status()["policy_observed_generation"] == gen
    # Idempotent sync
    again = b.sync_active_from_store()
    assert again is not None
    assert get_policy_bundle().content_digest == digest

    from app.governance_service import (
        GovernanceEvaluateRequest,
        evaluate_governance_request,
    )

    result = evaluate_governance_request(
        GovernanceEvaluateRequest(
            team="platform",
            owner="alice",
            environment="development",
            namespace="ai-dev",
            action="invoke_model",
            model="llama3.1:8b",
            provider="ollama",
        )
    )
    assert result.final_verdict in {"allow", "block", "approval_required"}
    assert result.policy_digest == digest


def test_activate_invalid_raises(store: DecisionStore) -> None:
    with pytest.raises(KeyError):
        store.activate_policy_bundle("does-not-exist")
    store.upsert_policy_bundle_candidate(
        bundle_id="bad",
        content_digest="c0ffee",
        validation_status="error",
        error="nope",
        source_json={"type": "filesystem", "path": "/tmp"},
    )
    with pytest.raises(ValueError):
        store.activate_policy_bundle("bad")
    with pytest.raises(RuntimeError):
        store.rollback_policy_bundle()


def test_lifecycle_previous_list_impact_rollback_durable(
    store: DecisionStore, tmp_path: Path
) -> None:
    import shutil

    root_a = tmp_path / "gov-a"
    root_b = tmp_path / "gov-b"
    shutil.copytree(get_governance_root(), root_a)
    shutil.copytree(get_governance_root(), root_b)
    packs_b = root_b / "policy-packs" / "packs.yaml"
    packs_b.write_text(packs_b.read_text() + "\n# durable-policy-test\n")

    life = PolicyLifecycle(store=store)
    bundle_a = life.validate_from_path(root_a)
    life.activate(bundle_a.bundle_id)
    bundle_b = life.validate_from_path(root_b)
    assert bundle_a.content_digest != bundle_b.content_digest
    life.activate(bundle_b.bundle_id)
    assert store.get_previous_policy_bundle() is not None
    assert store.get_active_policy_bundle().content_digest == bundle_b.content_digest

    clear_policy_bundle()
    replica = PolicyLifecycle(store=store)
    replica.sync_active_from_store(force=True)
    prev = replica.previous()
    assert prev is not None
    assert prev.content_digest == bundle_a.content_digest
    assert isinstance(replica.list_candidates(), list)

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
    impact = replica.simulate(bundle_b.bundle_id, limit=20)
    assert impact.evaluated_decisions >= 1
    assert replica.impact(bundle_b.bundle_id) is not None
    cold = PolicyLifecycle(store=store)
    assert cold.impact(bundle_b.bundle_id) is not None

    rolled = replica.rollback()
    assert rolled.content_digest == bundle_a.content_digest
    assert store.get_active_policy_bundle().bundle_id == bundle_a.bundle_id


def test_validate_from_source_and_get_candidate_store(store: DecisionStore) -> None:
    from app.policy_source import PolicySource

    root = get_governance_root()
    life = PolicyLifecycle(store=store)
    life.ensure_bootstrapped()
    bundle = life.validate_from_source(
        PolicySource(type="filesystem", path=str(root))
    )
    assert bundle.validation_status == "ok"
    clear_policy_bundle()
    other = PolicyLifecycle(store=store)
    loaded = other.get_candidate(bundle.bundle_id)
    assert loaded is not None
    assert loaded.content_digest == bundle.content_digest
