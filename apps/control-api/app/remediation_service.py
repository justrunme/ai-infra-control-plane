"""Closed-loop RemediationProposal lifecycle (detect → approve → PR → verify).

The control plane never mutates production inventory or backends. It records
proposals, evaluates policy, persists GitOps PR drafts, and verifies runtime
drift after an operator (or Argo) applies the change.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from app.decision_store import (
    DecisionStore,
    RemediationProposalRecord,
    get_decision_store,
)
from app.drift_actions import DriftSuggestedAction, build_drift_actions
from app.drift_service import DriftStatus
from app.durable_governance import persist_evaluation
from app.governance_service import (
    GovernanceEvaluateRequest,
    evaluate_governance_request,
)
from app.probes import get_inventory_drift

RemediationStatus = Literal[
    "detected",
    "proposed",
    "policy_evaluated",
    "approved",
    "rejected",
    "pr_created",
    "applied",
    "verifying",
    "verified",
    "failed",
]

_TERMINAL = frozenset({"rejected", "verified", "failed"})

_ALLOWED: dict[str, frozenset[str]] = {
    "detected": frozenset({"proposed"}),
    "proposed": frozenset({"policy_evaluated"}),
    "policy_evaluated": frozenset({"approved", "rejected"}),
    "approved": frozenset({"pr_created"}),
    "pr_created": frozenset({"applied"}),
    "applied": frozenset({"verifying", "verified", "failed"}),
    "verifying": frozenset({"verified", "failed"}),
}


class RemediationError(ValueError):
    """Invalid remediation lifecycle transition or input."""


def _require_transition(current: str, target: str) -> None:
    allowed = _ALLOWED.get(current, frozenset())
    if target not in allowed:
        raise RemediationError(
            f"cannot transition remediation from {current} to {target}"
        )


def _select_action(
    status: DriftStatus,
    *,
    action_index: int | None,
    action_kind: str | None,
) -> DriftSuggestedAction:
    actions = build_drift_actions(status).actions
    actionable = [
        item
        for item in actions
        if item.kind
        in {"pull_model", "update_inventory", "open_github_pr", "reprobe"}
    ]
    if not actionable:
        raise RemediationError("no actionable drift remediations available")
    if action_index is not None:
        if action_index < 0 or action_index >= len(actionable):
            raise RemediationError("action_index out of range")
        return actionable[action_index]
    if action_kind:
        for item in actionable:
            if item.kind == action_kind:
                return item
        raise RemediationError(f"no remediation action with kind={action_kind}")
    # Prefer concrete model remediations over generic PR/issue helpers.
    for preferred in ("pull_model", "update_inventory", "reprobe", "open_github_pr"):
        for item in actionable:
            if item.kind == preferred:
                return item
    return actionable[0]


def create_from_drift(
    *,
    tenant_id: str = "platform",
    action_index: int | None = None,
    action_kind: str | None = None,
    environment: str = "production",
    drift: DriftStatus | None = None,
    store: DecisionStore | None = None,
) -> RemediationProposalRecord:
    """Detect inventory drift and open a proposal (status=proposed)."""
    del environment  # reserved for evaluate-policy defaults
    decision_store = store or get_decision_store()
    status = drift or get_inventory_drift()
    if status.in_sync:
        raise RemediationError("inventory is in sync; no remediation needed")
    action = _select_action(
        status, action_index=action_index, action_kind=action_kind
    )
    proposal_id = decision_store.create_remediation_proposal(
        tenant_id=tenant_id or "platform",
        status="proposed",
        source="inventory_drift",
        remediation_kind=action.kind,
        drift_snapshot=status.model_dump(),
        selected_action=action.model_dump(),
    )
    record = decision_store.get_remediation_proposal(proposal_id)
    assert record is not None
    return record


def evaluate_policy(
    proposal_id: str,
    *,
    tenant_id: str | None = None,
    environment: str = "production",
    team: str | None = None,
    store: DecisionStore | None = None,
) -> RemediationProposalRecord:
    decision_store = store or get_decision_store()
    record = decision_store.get_remediation_proposal(
        proposal_id, tenant_id=tenant_id
    )
    if record is None:
        raise KeyError(proposal_id)
    _require_transition(record.status, "policy_evaluated")

    action = record.selected_action or {}
    model = str(action.get("model") or "inventory-remediation")
    provider = str(action.get("backend") or "ollama")
    request = GovernanceEvaluateRequest(
        team=team or record.tenant_id or "platform",
        tenant_id=record.tenant_id or team or "platform",
        owner="remediation-bot",
        subject="remediation-bot",
        environment=environment,
        action="remediate_inventory",
        model=model,
        provider=provider,
        tool_access=True,
        write_permission=True,
        prompt_text=(
            f"Remediate inventory drift via {record.remediation_kind}: "
            f"{action.get('title', '')}"
        ),
    )
    result = evaluate_governance_request(request)
    persisted = persist_evaluation(
        result=result,
        request=request,
        request_id=f"remediation-{proposal_id}-{uuid.uuid4().hex[:8]}",
        store=decision_store,
    )

    # allow → auto-approved so operators can prepare a PR without a second hop
    if persisted.final_verdict == "allow":
        target_status: RemediationStatus = "approved"
    elif persisted.final_verdict == "block":
        target_status = "rejected"
    else:
        target_status = "policy_evaluated"

    return decision_store.update_remediation_proposal(
        proposal_id,
        status=target_status,
        decision_id=persisted.decision_id,
        approval_id=persisted.approval_id,
        policy_verdict=persisted.final_verdict,
    )


def resolve_proposal(
    proposal_id: str,
    *,
    approved: bool,
    reviewer: str,
    comment: str = "",
    tenant_id: str | None = None,
    store: DecisionStore | None = None,
) -> RemediationProposalRecord:
    decision_store = store or get_decision_store()
    record = decision_store.get_remediation_proposal(
        proposal_id, tenant_id=tenant_id
    )
    if record is None:
        raise KeyError(proposal_id)
    target: RemediationStatus = "approved" if approved else "rejected"
    _require_transition(record.status, target)

    if record.approval_id:
        decision_store.resolve_approval(
            record.approval_id,
            "approved" if approved else "rejected",
            reviewer=reviewer,
            comment=comment,
        )
        if record.decision_id:
            decision_store.append_audit_meta(
                decision_id=record.decision_id,
                event_type="remediation_resolved",
                actor=reviewer,
                payload={
                    "proposal_id": proposal_id,
                    "status": target,
                    "comment": comment,
                },
            )

    return decision_store.update_remediation_proposal(
        proposal_id,
        status=target,
    )


def prepare_pr_draft(
    proposal_id: str,
    *,
    tenant_id: str | None = None,
    pr_url: str | None = None,
    store: DecisionStore | None = None,
) -> RemediationProposalRecord:
    from app.gitops_provider import (
        GitOpsProviderError,
        GitOpsPullRequestRequest,
        get_gitops_provider,
    )

    decision_store = store or get_decision_store()
    record = decision_store.get_remediation_proposal(
        proposal_id, tenant_id=tenant_id
    )
    if record is None:
        raise KeyError(proposal_id)
    _require_transition(record.status, "pr_created")

    action = record.selected_action or {}
    drift = DriftStatus.model_validate(record.drift_snapshot)
    actions = build_drift_actions(drift).actions
    pr_action = next((a for a in actions if a.kind == "open_github_pr"), None)
    title = (
        str(action.get("pr_title") or "")
        or (pr_action.pr_title if pr_action else None)
        or f"fix: remediate inventory drift ({record.remediation_kind})"
    )
    body = (
        str(action.get("pr_body") or "")
        or (pr_action.pr_body if pr_action else None)
        or (
            "## Why\n\n"
            f"{drift.summary}\n\n"
            f"Selected action: {action.get('title', record.remediation_kind)}\n\n"
            "## Validation\n\n"
            "- [ ] `GET /drift` returns `in_sync: true`\n"
            f"- [ ] Remediation proposal `{proposal_id}` reaches `verified`\n"
        )
    )
    resolved_url = (pr_url or "").strip()
    if not resolved_url:
        try:
            result = get_gitops_provider().create_draft_pull_request(
                GitOpsPullRequestRequest(
                    proposal_id=proposal_id,
                    title=title,
                    body=body,
                    tenant_id=record.tenant_id,
                    remediation_kind=record.remediation_kind,
                )
            )
        except GitOpsProviderError as exc:
            raise RemediationError(str(exc)) from exc
        resolved_url = (result.pr_url or "").strip()
    return decision_store.update_remediation_proposal(
        proposal_id,
        status="pr_created",
        pr_title=title,
        pr_body=body,
        pr_url=resolved_url,
    )


def mark_applied(
    proposal_id: str,
    *,
    tenant_id: str | None = None,
    pr_url: str | None = None,
    store: DecisionStore | None = None,
) -> RemediationProposalRecord:
    from datetime import UTC, datetime

    decision_store = store or get_decision_store()
    record = decision_store.get_remediation_proposal(
        proposal_id, tenant_id=tenant_id
    )
    if record is None:
        raise KeyError(proposal_id)
    _require_transition(record.status, "applied")
    kwargs: dict[str, Any] = {
        "status": "applied",
        "applied_at": datetime.now(UTC).isoformat(),
    }
    if pr_url is not None:
        kwargs["pr_url"] = pr_url
    return decision_store.update_remediation_proposal(proposal_id, **kwargs)


def verify_runtime(
    proposal_id: str,
    *,
    tenant_id: str | None = None,
    drift: DriftStatus | None = None,
    store: DecisionStore | None = None,
) -> RemediationProposalRecord:
    decision_store = store or get_decision_store()
    record = decision_store.get_remediation_proposal(
        proposal_id, tenant_id=tenant_id
    )
    if record is None:
        raise KeyError(proposal_id)
    if record.status == "applied":
        _require_transition(record.status, "verifying")
        decision_store.update_remediation_proposal(
            proposal_id, status="verifying"
        )
    elif record.status != "verifying":
        _require_transition(record.status, "verified")

    status = drift or get_inventory_drift()
    snapshot = status.model_dump()
    if status.in_sync:
        return decision_store.update_remediation_proposal(
            proposal_id,
            status="verified",
            verification_snapshot=snapshot,
            failure_reason="",
        )
    return decision_store.update_remediation_proposal(
        proposal_id,
        status="failed",
        verification_snapshot=snapshot,
        failure_reason=status.summary or "inventory still drifting",
    )


def proposal_to_dict(record: RemediationProposalRecord) -> dict[str, Any]:
    return {
        "proposal_id": record.proposal_id,
        "tenant_id": record.tenant_id,
        "status": record.status,
        "source": record.source,
        "remediation_kind": record.remediation_kind,
        "drift_snapshot": record.drift_snapshot,
        "selected_action": record.selected_action,
        "decision_id": record.decision_id,
        "approval_id": record.approval_id,
        "policy_verdict": record.policy_verdict,
        "pr_title": record.pr_title,
        "pr_body": record.pr_body,
        "pr_url": record.pr_url,
        "applied_at": record.applied_at,
        "verification_snapshot": record.verification_snapshot,
        "failure_reason": record.failure_reason,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "terminal": record.status in _TERMINAL,
    }
