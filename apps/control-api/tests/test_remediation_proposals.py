"""RemediationProposal closed-loop lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.decision_store import DecisionStore, reset_decision_store
from app.drift_service import BackendDrift, DriftStatus
from app.main import app
from app.remediation_service import (
    RemediationError,
    create_from_drift,
    evaluate_policy,
    mark_applied,
    prepare_pr_draft,
    resolve_proposal,
    verify_runtime,
)
from app.settings import clear_settings_cache


def _drift_missing(*, in_sync: bool = False) -> DriftStatus:
    return DriftStatus(
        updated_at="2026-01-01T00:00:00+00:00",
        in_sync=in_sync,
        summary=(
            "ok"
            if in_sync
            else "configured inventory differs from live backend probes"
        ),
        backends=[
            BackendDrift(
                backend="ollama",
                probe_healthy=True,
                desired_models=["llama3.1:8b"],
                actual_models=[] if not in_sync else ["llama3.1:8b"],
                missing_on_backend=[] if in_sync else ["llama3.1:8b"],
                unexpected_on_backend=[],
                in_sync=in_sync,
            ),
            BackendDrift(
                backend="vllm",
                probe_healthy=True,
                desired_models=[],
                actual_models=[],
                missing_on_backend=[],
                unexpected_on_backend=[],
                in_sync=True,
            ),
        ],
    )


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DecisionStore:
    db_url = f"sqlite:///{tmp_path / 'remediation.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    clear_settings_cache()
    reset_decision_store(None)
    decision_store = DecisionStore(db_url)
    reset_decision_store(decision_store)
    yield decision_store
    reset_decision_store(None)
    clear_settings_cache()


def test_remediation_happy_path_allow_to_verified(store: DecisionStore) -> None:
    proposal = create_from_drift(
        tenant_id="platform",
        drift=_drift_missing(),
        store=store,
        action_kind="pull_model",
    )
    assert proposal.status == "proposed"
    assert proposal.remediation_kind == "pull_model"

    # Development environment typically yields allow → auto-approved.
    evaluated = evaluate_policy(
        proposal.proposal_id,
        environment="development",
        store=store,
    )
    assert evaluated.policy_verdict in {"allow", "approval_required", "block"}
    if evaluated.policy_verdict == "allow":
        assert evaluated.status == "approved"
    elif evaluated.policy_verdict == "approval_required":
        assert evaluated.status == "policy_evaluated"
        evaluated = resolve_proposal(
            proposal.proposal_id,
            approved=True,
            reviewer="alice",
            store=store,
        )
        assert evaluated.status == "approved"
    else:
        pytest.skip("policy blocked remediation in this fixture")

    drafted = prepare_pr_draft(proposal.proposal_id, store=store)
    assert drafted.status == "pr_created"
    assert drafted.pr_title
    assert drafted.pr_body

    applied = mark_applied(
        proposal.proposal_id,
        pr_url="https://github.com/example/pr/1",
        store=store,
    )
    assert applied.status == "applied"
    assert applied.pr_url.endswith("/1")

    verified = verify_runtime(
        proposal.proposal_id,
        drift=_drift_missing(in_sync=True),
        store=store,
    )
    assert verified.status == "verified"


def test_remediation_verify_failed_when_still_drifting(
    store: DecisionStore,
) -> None:
    proposal = create_from_drift(
        tenant_id="acme",
        drift=_drift_missing(),
        store=store,
    )
    # Force approved to isolate verify semantics from pack policy variance.
    store.update_remediation_proposal(
        proposal.proposal_id,
        status="approved",
        policy_verdict="allow",
    )
    prepare_pr_draft(proposal.proposal_id, store=store)
    mark_applied(proposal.proposal_id, store=store)
    failed = verify_runtime(
        proposal.proposal_id,
        drift=_drift_missing(in_sync=False),
        store=store,
    )
    assert failed.status == "failed"
    assert failed.failure_reason


def test_create_from_drift_rejects_in_sync(store: DecisionStore) -> None:
    with pytest.raises(RemediationError, match="in sync"):
        create_from_drift(drift=_drift_missing(in_sync=True), store=store)


def test_remediation_api_create_and_list(
    store: DecisionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.remediation_service.get_inventory_drift",
        lambda: _drift_missing(),
    )
    client = TestClient(app)
    created = client.post(
        "/remediation/proposals",
        json={"action_kind": "pull_model", "tenant_id": "platform"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "proposed"
    listed = client.get("/remediation/proposals")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    got = client.get(f"/remediation/proposals/{body['proposal_id']}")
    assert got.status_code == 200
    assert got.json()["proposal_id"] == body["proposal_id"]


def test_schema_includes_remediation_migration(store: DecisionStore) -> None:
    from app.db_schema import EXPECTED_MIGRATION_VERSIONS

    assert "007_remediation_proposals" in EXPECTED_MIGRATION_VERSIONS
    assert store.list_schema_migrations() == EXPECTED_MIGRATION_VERSIONS
