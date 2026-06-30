"""Unit tests for the AI approval workflow engine."""

from __future__ import annotations

from types import ModuleType


def approval_request(**overrides) -> dict:
    request = {
        "id": "req-1",
        "team": "platform",
        "owner": "alice",
        "environment": "dev",
        "namespace": "ai-dev",
        "action": "noop",
        "model": "llama3.1:8b",
        "provider": "ollama",
        "cost_decision": "allow",
        "cost_per_hour_usd": 0.10,
        "forecast_monthly_cost_usd": 100.0,
        "risk": "low",
    }
    request.update(overrides)
    return request


def test_low_risk_request_allows(approval_module: ModuleType) -> None:
    result = approval_module.evaluate_request(approval_request())
    assert result["decision"] == "allow"


def test_missing_owner_blocks(approval_module: ModuleType) -> None:
    result = approval_module.evaluate_request(approval_request(owner="none"))
    assert result["decision"] == "block"


def test_cost_block_blocks(approval_module: ModuleType) -> None:
    result = approval_module.evaluate_request(
        approval_request(cost_decision="block")
    )
    assert result["decision"] == "block"


def test_high_risk_requires_approval(approval_module: ModuleType) -> None:
    result = approval_module.evaluate_request(approval_request(risk="high"))
    assert result["decision"] == "approval_required"


def test_production_requires_approval(approval_module: ModuleType) -> None:
    result = approval_module.evaluate_request(
        approval_request(environment="production")
    )
    assert result["decision"] == "approval_required"


def test_external_provider_requires_approval(approval_module: ModuleType) -> None:
    result = approval_module.evaluate_request(approval_request(provider="openai"))
    assert result["decision"] == "approval_required"
