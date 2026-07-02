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
    quota_state_status,
    read_quota_state,
)


class GovernanceInputsStatus(BaseModel):
    quota: dict[str, object]
    prometheus: dict[str, object]


def enrich_governance_request(
    payload: GovernanceEvaluateRequest,
) -> tuple[GovernanceEvaluateRequest, QuotaStateSnapshot | None, PrometheusSignals]:
    updates: dict[str, object] = {}
    quota_snapshot = read_quota_state(payload.team)
    if quota_snapshot is not None:
        if payload.requests_last_minute == 0:
            updates["requests_last_minute"] = quota_snapshot.requests_last_minute
        if payload.tokens_today == 0:
            updates["tokens_today"] = quota_snapshot.tokens_today

    signals = fetch_prometheus_signals(team=payload.team, model=payload.model)
    merged = payload.model_copy(update=updates) if updates else payload
    return merged, quota_snapshot, signals


def build_telemetry_stage(
    payload: GovernanceEvaluateRequest,
    quota_snapshot: QuotaStateSnapshot | None,
    signals: PrometheusSignals,
) -> GovernanceTelemetryStage:
    return GovernanceTelemetryStage(
        quota_source=quota_snapshot.source if quota_snapshot else "request",
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
