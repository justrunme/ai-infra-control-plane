"""Persist governance decisions and approval lifecycle records."""

from __future__ import annotations

from typing import Any

from app.approval_binding import compute_request_digest
from app.capability_service import resolve_execution_capability_digests
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
    """Attach decision_id / approval_id and write durable records atomically."""
    decision_store = store or get_decision_store()
    stages_payload = {
        name: stage.model_dump() for name, stage in result.stages.items()
    }
    request_digest = compute_request_digest(request)
    agent_digest = result.agent_capability_digest or ""
    tools_digest = result.tools_capability_digest or ""
    if not agent_digest and not tools_digest:
        agent_digest, tools_digest = resolve_execution_capability_digests(
            agent=getattr(request, "agent", "") or "",
            tenant_id=request.tenant_id or request.team,
            store=decision_store,
        )
    actor = request.owner or request.subject or "system"
    approval_id = result.approval_id

    with decision_store.transaction() as conn:
        decision_id = decision_store.create_decision(
            final_verdict=result.final_verdict,
            request_id=request_id,
            policy_bundle_id=result.policy_bundle_id or "",
            policy_digest=result.policy_digest or "",
            team=request.team,
            tenant_id=request.tenant_id or request.team,
            environment=request.environment,
            model=request.model,
            subject=request.subject or request.owner,
            reasons=list(result.reasons),
            stages=stages_payload,
            request=request.model_dump(),
            request_digest=request_digest,
            agent_capability_digest=agent_digest,
            tools_capability_digest=tools_digest,
            conn=conn,
        )
        if result.final_verdict == "approval_required" and not approval_id:
            approval_id = decision_store.create_approval(
                decision_id,
                ttl_seconds=get_settings().approval_ttl_seconds,
                conn=conn,
            )
            decision_store.append_audit_meta(
                decision_id=decision_id,
                event_type="approval_created",
                actor=actor,
                payload={
                    "approval_id": approval_id,
                    "request_digest": request_digest,
                },
                conn=conn,
            )
        decision_store.append_audit_meta(
            decision_id=decision_id,
            event_type="decision_recorded",
            actor=actor,
            payload={
                "final_verdict": result.final_verdict,
                "request_id": request_id,
                "approval_id": approval_id,
                "request_digest": request_digest,
            },
            conn=conn,
        )

    return result.model_copy(
        update={
            "decision_id": decision_id,
            "approval_id": approval_id,
            "agent_capability_digest": agent_digest or None,
            "tools_capability_digest": tools_digest or None,
        }
    )


def approval_grants_allow(
    approval_id: str,
    request: GovernanceEvaluateRequest,
    *,
    policy_digest: str = "",
    store: DecisionStore | None = None,
) -> bool:
    """Return True when approval is bound, unused, and matches this request.

    Checks:
    - approval status is ``approved`` and not expired
    - approval has not been consumed (one-time use)
    - current request digest matches the approved decision request digest
    - current policy digest matches the approved decision policy digest
    - active capability digests match when both sides are pinned

    Consume + audit are committed in one transaction.
    """
    decision_store = store or get_decision_store()
    approval = decision_store.get_approval(approval_id)
    if approval is None or approval.status != "approved":
        return False
    if approval.used_at:
        return False

    decision = decision_store.get_decision(approval.decision_id)
    if decision is None:
        return False

    current_digest = compute_request_digest(request)
    approved_digest = decision.request_digest or compute_request_digest(
        decision.request
    )
    if not approved_digest or current_digest != approved_digest:
        return False

    if (
        policy_digest
        and decision.policy_digest
        and policy_digest != decision.policy_digest
    ):
        return False

    agent_digest, tools_digest = resolve_execution_capability_digests(
        agent=getattr(request, "agent", "") or "",
        tenant_id=request.tenant_id or request.team,
        store=decision_store,
    )
    if (
        agent_digest
        and decision.agent_capability_digest
        and agent_digest != decision.agent_capability_digest
    ):
        return False
    if (
        tools_digest
        and decision.tools_capability_digest
        and tools_digest != decision.tools_capability_digest
    ):
        return False

    with decision_store.transaction() as conn:
        if not decision_store.consume_approval(approval_id, conn=conn):
            return False
        decision_store.append_audit_meta(
            decision_id=decision.decision_id,
            event_type="approval_consumed",
            actor=request.owner or request.subject or "system",
            payload={
                "approval_id": approval_id,
                "request_digest": current_digest,
            },
            conn=conn,
        )
    return True


def decision_to_dict(
    decision_id: str,
    store: DecisionStore | None = None,
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    decision_store = store or get_decision_store()
    record = decision_store.get_decision(decision_id, tenant_id=tenant_id)
    if record is None:
        raise KeyError(decision_id)
    return {
        "decision_id": record.decision_id,
        "request_id": record.request_id,
        "final_verdict": record.final_verdict,
        "policy_bundle_id": record.policy_bundle_id,
        "policy_digest": record.policy_digest,
        "agent_capability_digest": record.agent_capability_digest,
        "tools_capability_digest": record.tools_capability_digest,
        "team": record.team,
        "tenant_id": record.tenant_id,
        "environment": record.environment,
        "model": record.model,
        "subject": record.subject,
        "reasons": record.reasons,
        "stages": record.stages,
        "request": record.request,
        "request_digest": record.request_digest,
        "created_at": record.created_at,
    }
