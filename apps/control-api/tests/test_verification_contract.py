"""Runtime verification contract (v2.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.decision_store import DecisionStore, reset_decision_store
from app.drift_service import BackendDrift, DriftStatus
from app.remediation_service import mark_applied, prepare_pr_draft, verify_runtime
from app.settings import clear_settings_cache
from app.verification_contract import (
    SCHEMA_VERSION,
    build_baseline_closure,
    build_verification_snapshot,
)


def _drift(*, in_sync: bool, missing: list[str] | None = None) -> DriftStatus:
    missing = missing or ([] if in_sync else ["llama3.1:8b"])
    return DriftStatus(
        updated_at="2026-01-01T00:00:00+00:00",
        in_sync=in_sync,
        summary="ok" if in_sync else "still drifting",
        backends=[
            BackendDrift(
                backend="ollama",
                probe_healthy=True,
                desired_models=["llama3.1:8b"],
                actual_models=[] if missing else ["llama3.1:8b"],
                missing_on_backend=missing,
                unexpected_on_backend=[],
                in_sync=in_sync,
            )
        ],
    )


def test_baseline_closure_resolves_missing() -> None:
    baseline = _drift(in_sync=False, missing=["llama3.1:8b"]).model_dump()
    current = _drift(in_sync=True, missing=[])
    closure = build_baseline_closure(
        baseline_snapshot=baseline, current=current
    )
    assert closure.closed is True
    assert closure.resolved == ["llama3.1:8b"]
    assert closure.still_missing == []


def test_baseline_closure_still_missing() -> None:
    baseline = _drift(in_sync=False, missing=["llama3.1:8b"]).model_dump()
    current = _drift(in_sync=False, missing=["llama3.1:8b"])
    closure = build_baseline_closure(
        baseline_snapshot=baseline, current=current
    )
    assert closure.closed is False
    assert closure.still_missing == ["llama3.1:8b"]


def test_build_snapshot_dual_write_aliases() -> None:
    inventory = _drift(in_sync=True, missing=[])
    snapshot = build_verification_snapshot(
        proposal_id="p1",
        inventory=inventory,
        baseline_snapshot=_drift(in_sync=False).model_dump(),
        probe_fresh=True,
    )
    assert snapshot.schema_version == SCHEMA_VERSION
    assert snapshot.outcome == "verified"
    assert snapshot.gitops_sync == "not_checked"
    payload = snapshot.to_persist_dict()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["in_sync"] is True
    assert payload["summary"] == "ok"
    assert isinstance(payload["backends"], list)
    names = {check.name for check in snapshot.checks}
    assert names == {"probe_freshness", "inventory_drift", "baseline_closure"}


def test_verify_runtime_persists_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'verify.db'}")
    clear_settings_cache()
    reset_decision_store(None)
    store = DecisionStore.from_env()
    reset_decision_store(store)

    baseline = _drift(in_sync=False, missing=["llama3.1:8b"])
    proposal_id = store.create_remediation_proposal(
        tenant_id="platform",
        status="approved",
        source="test",
        remediation_kind="pull_model",
        drift_snapshot=baseline.model_dump(),
        selected_action={"kind": "pull_model", "title": "Pull"},
    )
    prepare_pr_draft(proposal_id, store=store)
    mark_applied(proposal_id, store=store)
    verified = verify_runtime(
        proposal_id,
        drift=_drift(in_sync=True, missing=[]),
        store=store,
    )
    assert verified.status == "verified"
    snap = verified.verification_snapshot or {}
    assert snap["schema_version"] == SCHEMA_VERSION
    assert snap["outcome"] == "verified"
    assert snap["in_sync"] is True
    assert any(c["name"] == "baseline_closure" for c in snap["checks"])

    reset_decision_store(None)
    store.close()
    clear_settings_cache()


def test_verify_fails_when_baseline_not_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'verify2.db'}")
    clear_settings_cache()
    reset_decision_store(None)
    store = DecisionStore.from_env()
    reset_decision_store(store)

    proposal_id = store.create_remediation_proposal(
        tenant_id="platform",
        status="approved",
        source="test",
        remediation_kind="pull_model",
        drift_snapshot=_drift(in_sync=False, missing=["llama3.1:8b"]).model_dump(),
        selected_action={"kind": "pull_model"},
    )
    prepare_pr_draft(proposal_id, store=store)
    mark_applied(proposal_id, store=store)
    # Global in_sync true but baseline model still missing on a backend —
    # construct inventory that reports in_sync False via missing.
    failed = verify_runtime(
        proposal_id,
        drift=_drift(in_sync=False, missing=["llama3.1:8b"]),
        store=store,
    )
    assert failed.status == "failed"
    snap = failed.verification_snapshot or {}
    assert snap["schema_version"] == SCHEMA_VERSION
    assert snap["outcome"] == "failed"

    reset_decision_store(None)
    store.close()
    clear_settings_cache()
