"""Query Prometheus for live governance telemetry inputs."""

from __future__ import annotations

import os
from typing import Any

import httpx
from pydantic import BaseModel, Field


class PrometheusSignals(BaseModel):
    enabled: bool = False
    team: str = ""
    model: str = ""
    gateway_p95_latency_ms: float | None = None
    gateway_error_rate: float | None = None
    governance_block_rate: float | None = None
    tenant_request_rate: float | None = None
    queries: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class PrometheusStatus(BaseModel):
    enabled: bool
    url: str | None = None
    max_error_rate: float = 0.05
    max_p95_latency_ms: float = 2500.0


def is_prometheus_enabled() -> bool:
    return os.getenv("PROMETHEUS_GOVERNANCE_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def get_prometheus_url() -> str | None:
    url = os.getenv("PROMETHEUS_URL", "").strip().rstrip("/")
    return url or None


def get_max_error_rate() -> float:
    return float(os.getenv("PROMETHEUS_MAX_ERROR_RATE", "0.05"))


def get_max_p95_latency_ms() -> float:
    return float(os.getenv("PROMETHEUS_MAX_P95_LATENCY_MS", "2500"))


def prometheus_status() -> PrometheusStatus:
    return PrometheusStatus(
        enabled=is_prometheus_enabled() and bool(get_prometheus_url()),
        url=get_prometheus_url(),
        max_error_rate=get_max_error_rate(),
        max_p95_latency_ms=get_max_p95_latency_ms(),
    )


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _instant_query(client: httpx.Client, promql: str) -> float | None:
    response = client.get("/api/v1/query", params={"query": promql})
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "success":
        raise ValueError(payload.get("error", "prometheus query failed"))

    result = payload.get("data", {}).get("result", [])
    if not result:
        return None

    value = result[0].get("value", [None, None])[1]
    if value is None:
        return None
    return float(value)


def fetch_prometheus_signals(*, team: str, model: str) -> PrometheusSignals:
    base_url = get_prometheus_url()
    if not is_prometheus_enabled() or not base_url:
        return PrometheusSignals(enabled=False, team=team, model=model)

    team_label = _escape_label(team)
    model_label = _escape_label(model)
    queries = {
        "gateway_p95_latency_ms": (
            "histogram_quantile(0.95, sum(rate(gateway_chat_duration_seconds_bucket"
            f'{{team="{team_label}"}}[5m])) by (le)) * 1000'
        ),
        "gateway_error_rate": (
            f'sum(rate(gateway_chat_errors_total{{team="{team_label}"}}[5m])) '
            "/ clamp_min(sum(rate(gateway_chat_requests_total"
            f'{{team="{team_label}"}}[5m])), 1)'
        ),
        "governance_block_rate": (
            'sum(rate(gateway_governance_decisions_total{verdict="block"}[5m])) '
            "/ clamp_min(sum(rate(gateway_governance_decisions_total[5m])), 1)"
        ),
        "tenant_request_rate": (
            f'sum(rate(gateway_tenant_requests_total{{team="{team_label}"}}[5m]))'
        ),
    }
    if model:
        queries["gateway_p95_latency_ms"] = (
            "histogram_quantile(0.95, sum(rate(gateway_chat_duration_seconds_bucket"
            f'{{team="{team_label}",model="{model_label}"}}[5m])) by (le)) * 1000'
        )

    signals = PrometheusSignals(
        enabled=True,
        team=team,
        model=model,
        queries=queries,
    )
    timeout = float(os.getenv("PROMETHEUS_TIMEOUT_SECONDS", "2.0"))

    try:
        with httpx.Client(base_url=base_url, timeout=timeout) as client:
            for name, promql in queries.items():
                try:
                    value = _instant_query(client, promql)
                except (httpx.HTTPError, ValueError, TypeError) as error:
                    signals.errors.append(f"{name}: {error}")
                    continue
                setattr(signals, name, value)
    except httpx.HTTPError as error:
        signals.errors.append(f"prometheus: {error}")

    return signals


def prometheus_block_reasons(signals: PrometheusSignals) -> list[str]:
    if not signals.enabled:
        return []

    reasons: list[str] = []
    if (
        signals.gateway_error_rate is not None
        and signals.gateway_error_rate > get_max_error_rate()
    ):
        reasons.append(
            "live prometheus gateway_error_rate exceeded threshold "
            f"({signals.gateway_error_rate:.3f}>{get_max_error_rate():.3f})"
        )
    if (
        signals.gateway_p95_latency_ms is not None
        and signals.gateway_p95_latency_ms > get_max_p95_latency_ms()
    ):
        reasons.append(
            "live prometheus gateway_p95_latency_ms exceeded threshold "
            f"({signals.gateway_p95_latency_ms:.0f}>{get_max_p95_latency_ms():.0f})"
        )
    return reasons


def signals_to_row_fields(signals: PrometheusSignals) -> dict[str, Any]:
    fields: dict[str, Any] = {"prometheus_enabled": signals.enabled}
    if signals.gateway_p95_latency_ms is not None:
        fields["gateway_p95_latency_ms"] = signals.gateway_p95_latency_ms
    if signals.gateway_error_rate is not None:
        fields["gateway_error_rate"] = signals.gateway_error_rate
    if signals.governance_block_rate is not None:
        fields["governance_block_rate"] = signals.governance_block_rate
    if signals.tenant_request_rate is not None:
        fields["tenant_request_rate"] = signals.tenant_request_rate
    return fields
