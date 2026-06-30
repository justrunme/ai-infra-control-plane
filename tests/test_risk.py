"""Unit tests for the AI request risk scoring engine."""

from __future__ import annotations

from types import ModuleType


def base_request(**overrides) -> dict:
    request = {
        "id": "req-1",
        "team": "platform",
        "owner": "alice",
        "environment": "dev",
        "namespace": "ai-dev",
        "action": "noop",
        "model": "llama3.1:8b",
        "provider": "ollama",
        "input_tokens": 100,
        "output_tokens": 100,
        "forecast_monthly_cost_usd": 50.0,
        "sensitive_data": False,
        "tool_access": False,
        "write_permission": False,
    }
    request.update(overrides)
    return request


def test_risk_level_boundaries(risk_module: ModuleType, risk_rules: dict) -> None:
    thresholds = risk_rules["thresholds"]
    assert risk_module.risk_level(0, thresholds) == "low"
    assert risk_module.risk_level(24, thresholds) == "low"
    assert risk_module.risk_level(25, thresholds) == "medium"
    assert risk_module.risk_level(50, thresholds) == "high"
    assert risk_module.risk_level(75, thresholds) == "critical"


def test_clean_request_scores_low(risk_module: ModuleType, risk_rules: dict) -> None:
    result = risk_module.evaluate_request(base_request(), risk_rules)
    assert result["score"] == 0
    assert result["level"] == "low"
    assert result["factors"] == []


def test_high_risk_request_is_critical(
    risk_module: ModuleType, risk_rules: dict
) -> None:
    request = base_request(
        owner="",
        provider="openai",
        environment="production",
        sensitive_data=True,
    )
    result = risk_module.evaluate_request(request, risk_rules)
    # missing_owner (25) + external_provider (18) + production (20) + sensitive (18)
    assert result["score"] == 81
    assert result["level"] == "critical"
    factor_names = {factor["name"] for factor in result["factors"]}
    assert {
        "missing_owner",
        "external_provider",
        "production_namespace",
        "sensitive_data",
    } == factor_names


def test_score_is_capped_at_100(risk_module: ModuleType, risk_rules: dict) -> None:
    request = base_request(
        owner="",
        provider="openai",
        environment="production",
        namespace="ai-prod",
        action="deploy_model",
        input_tokens=40000,
        output_tokens=40000,
        forecast_monthly_cost_usd=5000.0,
        sensitive_data=True,
        tool_access=True,
        write_permission=True,
    )
    result = risk_module.evaluate_request(request, risk_rules)
    assert result["score"] == 100
    assert result["level"] == "critical"
