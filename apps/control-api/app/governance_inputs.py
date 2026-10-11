"""Merge Redis quota state and Prometheus telemetry into governance requests."""

from __future__ import annotations

from pydantic import BaseModel

from app.governance_service import GovernanceEvaluateRequest
from app.governance_telemetry import GovernanceTelemetryStage
from app.prometheus_service import (
    PrometheusSignals,
    fetch_prometheus_signals,
    prometheus_block_reasons,
    prometheus_status,
    signals_to_row_fields,
)
from app.quota_state_service import (
    QuotaStateSnapshot,
    get_quota_on_unavailable,
    quota_state_status,
    read_quota_state,
)
from app.server_signals import (
    allow_client_governance_signals,
    derive_request_cost,
    derive_sensitivity,
)


class GovernanceInputsStatus(BaseModel):
    quota: dict[str, object]
    prometheus: dict[str, object]


def enrich_governance_request(
    payload: GovernanceEvaluateRequest,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[GovernanceEvaluateRequest, QuotaStateSnapshot | None, PrometheusSignals]:
    """Overlay server-authoritative quota/cost/sensitivity onto the request.

    Client-supplied ``requests_last_minute``, ``tokens_today``, cost fields,
    ``sensitive_data``, and ``write_permission`` are ignored unless simulate
    mode is allowed (demo / ``governance-simulate`` role).
    """
    headers = headers or {}
    simulate = allow_client_governance_signals(headers)
    updates: dict[str, object] = {}
    quota_snapshot = read_quota_state(payload.team)

    if quota_snapshot is not None and not quota_snapshot.unavailable:
        # Always prefer Redis counters; never trust the client body.
        updates["requests_last_minute"] = quota_snapshot.requests_last_minute
        updates["tokens_today"] = quota_snapshot.tokens_today
        month_cost = quota_snapshot.month_to_date_cost_usd
    elif quota_snapshot is not None and quota_snapshot.unavailable:
        # Leave counters unset; evaluate_governance_request applies onUnavailable.
        month_cost = None
    elif simulate:
        # Redis disabled + simulate/playground: keep client counters.
        month_cost = None
    else:
        # Redis disabled in production: treat as unavailable.
        quota_snapshot = QuotaStateSnapshot(
            team=payload.team,
            source="unavailable",
            unavailable=True,
        )
        month_cost = None

    if not simulate:
        cost = derive_request_cost(
            model=payload.model,
            input_tokens=payload.input_tokens,
            output_tokens=payload.output_tokens,
            month_to_date_cost_usd=month_cost,
        )
        updates.update(cost)
        sensitivity = derive_sensitivity(
            team=payload.team,
            namespace=payload.namespace,
            headers=headers,
        )
        updates.update(sensitivity)

    signals = fetch_prometheus_signals(team=payload.team, model=payload.model)
    merged = payload.model_copy(update=updates) if updates else payload
    return merged, quota_snapshot, signals


def build_telemetry_stage(
    payload: GovernanceEvaluateRequest,
    quota_snapshot: QuotaStateSnapshot | None,
    signals: PrometheusSignals,
) -> GovernanceTelemetryStage:
    if quota_snapshot is None:
        quota_source = "request"
    elif quota_snapshot.unavailable:
        quota_source = "unavailable"
    else:
        quota_source = quota_snapshot.source
    return GovernanceTelemetryStage(
        quota_source=quota_source,
        requests_last_minute=payload.requests_last_minute,
        tokens_today=payload.tokens_today,
        prometheus_enabled=signals.enabled,
        gateway_p95_latency_ms=signals.gateway_p95_latency_ms,
        gateway_error_rate=signals.gateway_error_rate,
        governance_block_rate=signals.governance_block_rate,
        tenant_request_rate=signals.tenant_request_rate,
        prometheus_errors=list(signals.errors),
        block_reasons=prometheus_block_reasons(signals),
    )


def governance_inputs_status() -> GovernanceInputsStatus:
    quota = quota_state_status()
    prom = prometheus_status()
    return GovernanceInputsStatus(
        quota=quota.model_dump(),
        prometheus=prom.model_dump(),
    )


def apply_prometheus_row_fields(
    row: dict[str, object],
    signals: PrometheusSignals,
) -> None:
    row.update(signals_to_row_fields(signals))


# Re-export for callers that need the policy when Redis is missing.
__all__ = [
    "GovernanceInputsStatus",
    "apply_prometheus_row_fields",
    "build_telemetry_stage",
    "enrich_governance_request",
    "get_quota_on_unavailable",
    "governance_inputs_status",
]
