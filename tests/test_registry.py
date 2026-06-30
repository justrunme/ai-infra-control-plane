"""Unit tests for the model risk registry."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "governance/registry/models.yaml"


def test_parse_registry_loads_models(registry_module: ModuleType) -> None:
    registry = registry_module.parse_registry(REGISTRY_PATH)
    assert "llama3.1:8b" in registry
    assert registry["llama3.1:8b"]["risk_tier"] == "low"
    assert "ai-prod" in registry["llama3.1:8b"]["allowed_namespaces"]


def test_forbidden_model_is_blocked(registry_module: ModuleType) -> None:
    registry = registry_module.parse_registry(REGISTRY_PATH)
    result = registry_module.evaluate_model_policy(
        {
            "model": "unknown-frontier-model",
            "namespace": "ai-dev",
            "sensitive_data": False,
            "forecast_monthly_cost_usd": 100,
        },
        registry,
    )
    assert result["forbidden"] is True


def test_namespace_violation_blocks(registry_module: ModuleType) -> None:
    registry = registry_module.parse_registry(REGISTRY_PATH)
    result = registry_module.evaluate_model_policy(
        {
            "model": "gpt-4.1-mini",
            "namespace": "ai-dev",
            "sensitive_data": False,
            "forecast_monthly_cost_usd": 100,
        },
        registry,
    )
    assert result["forbidden"] is True
    assert any("namespace" in reason for reason in result["reasons"])
