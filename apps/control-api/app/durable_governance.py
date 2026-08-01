"""Persist governance decisions and approval lifecycle records."""

from __future__ import annotations

from typing import Any

from app.decision_store import DecisionStore, get_decision_store
from app.governance_service import (
    GovernanceEvaluateRequest,
    GovernanceEvaluateResponse,
)
from app.settings import get_settings


def persist_evaluation(
    *,
    result: GovernanceEvaluateResponse,
    request: GovernanceEvaluateRequest,
    request_id: str,
    store: DecisionStore | None = None,
) -> GovernanceEvaluateResponse:
    """Attach decision_id / approval_id and write durable records."""
    decision_store = store or get_decision_store()
    stages_payload = {
        name: stage.model_dump() for name, stage in result.stages.items()
    }
    decision_id = decision_store.create_decision(
        final_verdict=result.final_verdict,
        request_id=request_id,
        policy_bundle_id=result.policy_bundle_id or "",
        policy_digest=result.policy_digest or "",
        team=request.team,
        environment=request.environment,
        model=request.model,
        subject=request.subject or request.owner,
        reasons=list(result.reasons),
        stages=stages_payload,
        request=request.model_dump(),
    )
    approval_id = result.approval_id
    if result.final_verdict == "approval_required" and not approval_id:
        approval_id = decision_store.create_approval(
            decision_id,
            ttl_seconds=get_settings().approval_ttl_seconds,
        )
        decision_store.append_audit_meta(
            decision_id=decision_id,
            event_type="approval_created",
            actor=request.owner or request.subject or "system",
            payload={"approval_id": approval_id},
        )
    decision_store.append_audit_meta(
        decision_id=decision_id,
        event_type="decision_recorded",
        actor=request.owner or request.subject or "system",
        payload={
            "final_verdict": result.final_verdict,
            "request_id": request_id,
            "approval_id": approval_id,
        },
    )
    return result.model_copy(
        update={"decision_id": decision_id, "approval_id": approval_id}
    )


def approval_grants_allow(approval_id: str, store: DecisionStore | None = None) -> bool:
    """Return True when a durable approval is approved and usable."""
    decision_store = store or get_decision_store()
    approval = decision_store.get_approval(approval_id)
    return approval is not None and approval.status == "approved"


def decision_to_dict(
    decision_id: str,
    store: DecisionStore | None = None,
) -> dict[str, Any]:
    decision_store = store or get_decision_store()
    record = decision_store.get_decision(decision_id)
    if record is None:
        raise KeyError(decision_id)
    return {
        "decision_id": record.decision_id,
        "request_id": record.request_id,
        "final_verdict": record.final_verdict,
        "policy_bundle_id": record.policy_bundle_id,
        "policy_digest": record.policy_digest,
        "team": record.team,
        "environment": record.environment,
        "model": record.model,
        "subject": record.subject,
        "reasons": record.reasons,
        "stages": record.stages,
        "request": record.request,
        "created_at": record.created_at,
    }
