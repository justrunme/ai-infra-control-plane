"""Immutable governance audit trail for enterprise compliance demos."""

from __future__ import annotations

import os
import uuid
from collections import deque
from datetime import UTC, datetime
from threading import Lock

from pydantic import BaseModel, Field

from app.governance_service import GovernanceEvaluateRequest, GovernanceEvaluateResponse
from app.identity_service import WorkloadIdentity


class AuditEvent(BaseModel):
    event_id: str
    timestamp: str
    event_type: str = "governance_evaluate"
    subject: str
    team: str
    owner: str
    environment: str
    namespace: str
    model: str
    action: str
    policy_pack: str = ""
    final_verdict: str
    reasons: list[str] = Field(default_factory=list)
    blocking_stage: str | None = None
    identity_source: str = "default"
    groups: list[str] = Field(default_factory=list)
    request_id: str | None = None


def blocking_stage_from_response(
    response: GovernanceEvaluateResponse,
) -> str | None:
    if response.final_verdict == "allow":
        return None

    for stage_name in ("policy_pack", "quota", "registry", "cost", "approval"):
        stage = response.stages.get(stage_name)
        if stage is not None and stage.decision == "block":
            return stage_name

    risk = response.stages.get("risk")
    if risk is not None and risk.level == "critical":
        return "risk"

    if response.final_verdict == "approval_required":
        approval = response.stages.get("approval")
        if approval is not None and approval.decision == "approval_required":
            return "approval"
        cost = response.stages.get("cost")
        if cost is not None and cost.decision == "warn":
            return "cost"
        return "approval"

    return None


class AuditStore:
    def __init__(self, max_events: int = 1000) -> None:
        self._max_events = max_events
        self._events: deque[AuditEvent] = deque(maxlen=max_events)
        self._lock = Lock()

    def record_governance_evaluate(
        self,
        *,
        identity: WorkloadIdentity,
        request: GovernanceEvaluateRequest,
        response: GovernanceEvaluateResponse,
        request_id: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            subject=identity.subject,
            team=identity.team,
            owner=identity.owner,
            environment=request.environment,
            namespace=request.namespace,
            model=request.model,
            action=request.action,
            policy_pack=request.policy_pack or response.policy_pack,
            final_verdict=response.final_verdict,
            reasons=list(response.reasons),
            blocking_stage=blocking_stage_from_response(response),
            identity_source=identity.source,
            groups=list(identity.groups),
            request_id=request_id,
        )
        with self._lock:
            self._events.append(event)
        from app.audit_sink import AUDIT_SINK

        AUDIT_SINK.persist(event)
        return event

    def list_events(
        self,
        *,
        limit: int = 50,
        team: str | None = None,
        subject: str | None = None,
        verdict: str | None = None,
    ) -> list[AuditEvent]:
        with self._lock:
            events = list(self._events)

        if team:
            events = [event for event in events if event.team == team]
        if subject:
            events = [event for event in events if event.subject == subject]
        if verdict:
            events = [event for event in events if event.final_verdict == verdict]

        events.reverse()
        return events[:limit]


def get_audit_store() -> AuditStore:
    max_events = int(os.getenv("AUDIT_MAX_EVENTS", "1000"))
    return AuditStore(max_events=max_events)


AUDIT_STORE = get_audit_store()
