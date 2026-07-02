"""Tests for Prometheus governance telemetry queries."""

from __future__ import annotations

import httpx

from app.prometheus_service import (
    _build_prometheus_queries,
    fetch_prometheus_signals,
    prometheus_block_reasons,
)


def test_build_prometheus_queries_match_runtime_metric_labels() -> None:
    queries = _build_prometheus_queries(team="finance", model="llama3.1:8b")

    assert "gateway_chat_errors_total" not in queries["gateway_error_rate"]
    assert 'outcome="error"' in queries["gateway_error_rate"]
    assert 'requested_model="llama3.1:8b"' in queries["gateway_error_rate"]
    assert 'team="finance"' in queries["tenant_request_rate"]
    assert "team=" not in queries["gateway_p95_latency_ms"]
    assert "model=" not in queries["gateway_p95_latency_ms"]

    without_model = _build_prometheus_queries(team="finance", model="")
    assert 'outcome="error"' in without_model["gateway_error_rate"]
    assert "requested_model=" not in without_model["gateway_error_rate"]


def test_fetch_prometheus_signals_parses_instant_query(monkeypatch) -> None:
    monkeypatch.setenv("PROMETHEUS_GOVERNANCE_ENABLED", "true")
    monkeypatch.setenv("PROMETHEUS_URL", "http://prometheus.test")

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params.get("query", "")
        if "gateway_chat_duration_seconds_bucket" in query:
            value = "2500"
        elif 'outcome="error"' in query:
            value = "0.12"
        elif "gateway_governance_decisions_total" in query:
            value = "0.03"
        else:
            value = "4.5"
        return httpx.Response(
            200,
            json={"status": "success", "data": {"result": [{"value": [1, value]}]}},
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr("app.prometheus_service.httpx.Client", client_factory)

    signals = fetch_prometheus_signals(team="finance", model="llama3.1:8b")
    assert signals.enabled is True
    assert signals.gateway_p95_latency_ms == 2500.0
    assert signals.gateway_error_rate == 0.12
    assert signals.tenant_request_rate == 4.5
    assert signals.errors == []


def test_prometheus_block_reasons_trigger_on_threshold(monkeypatch) -> None:
    monkeypatch.setenv("PROMETHEUS_MAX_ERROR_RATE", "0.05")
    monkeypatch.setenv("PROMETHEUS_MAX_P95_LATENCY_MS", "2000")

    from app.prometheus_service import PrometheusSignals

    signals = PrometheusSignals(
        enabled=True,
        gateway_error_rate=0.2,
        gateway_p95_latency_ms=3000,
    )
    reasons = prometheus_block_reasons(signals)
    assert len(reasons) == 2
