"""Unit-of-work persistence for decision/approval/audit writes."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.approval_binding import compute_request_digest
from app.decision_store import DecisionStore, reset_decision_store
from app.durable_governance import approval_grants_allow, persist_evaluation
from app.governance_service import GovernanceEvaluateRequest, GovernanceEvaluateResponse


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DecisionStore:
    db_path = tmp_path / "tx.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    reset_decision_store(None)
    instance = DecisionStore.from_env()
    reset_decision_store(instance)
    yield instance
    reset_decision_store(None)
    instance.close()


def _request() -> GovernanceEvaluateRequest:
    return GovernanceEvaluateRequest(
        team="platform",
        owner="alice",
        environment="development",
        namespace="ai-dev",
        action="invoke_model",
        model="llama3.1:8b",
        provider="ollama",
    )


def test_persist_evaluation_is_atomic(store: DecisionStore) -> None:
    request = _request()
    result = GovernanceEvaluateResponse(
        final_verdict="approval_required",
        policy_pack="default",
        reasons=["needs approval"],
        flow=["request", "final_verdict"],
        stages={},
    )
    persisted = persist_evaluation(
        result=result, request=request, request_id="req-1", store=store
    )
    assert persisted.decision_id
    assert persisted.approval_id
    assert store.get_decision(persisted.decision_id) is not None
    assert store.get_approval(persisted.approval_id) is not None


def test_approval_consume_rolls_back_when_audit_fails(
    store: DecisionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request()
    digest = compute_request_digest(request)
    decision_id = store.create_decision(
        final_verdict="approval_required",
        team="platform",
        model="llama3.1:8b",
        request=request.model_dump(),
        request_digest=digest,
        policy_digest="policy-v1",
    )
    approval_id = store.create_approval(decision_id, ttl_seconds=600)
    store.resolve_approval(approval_id, status="approved", reviewer="bob")

    def _boom(**kwargs):
        if kwargs.get("event_type") == "approval_consumed":
            raise RuntimeError("audit write failed")
        return DecisionStore.append_audit_meta(store, **kwargs)

    monkeypatch.setattr(store, "append_audit_meta", _boom)

    with pytest.raises(RuntimeError, match="audit write failed"):
        approval_grants_allow(
            approval_id, request, policy_digest="policy-v1", store=store
        )

    approval = store.get_approval(approval_id)
    assert approval is not None
    assert approval.status == "approved"
    assert approval.used_at is None
