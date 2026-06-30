"""Unit tests for the AI cost governance engine."""

from __future__ import annotations

from types import ModuleType


def usage_row(**overrides) -> dict:
    row = {
        "timestamp": "2026-01-01T00:00:00Z",
        "team": "platform",
        "model": "llama3.1:8b",
        "provider": "ollama",
        "input_tokens": 100,
        "output_tokens": 100,
        "cost_per_request_usd": 0.01,
        "cost_per_hour_usd": 0.50,
        "month_to_date_cost_usd": 100.0,
        "forecast_monthly_cost_usd": 1000.0,
    }
    row.update(overrides)
    return row


def test_usage_within_limits_allows(
    cost_module: ModuleType, cost_policies: dict
) -> None:
    result = cost_module.evaluate_row(usage_row(), cost_policies)
    assert result["decision"] == "allow"


def test_near_budget_warns(cost_module: ModuleType, cost_policies: dict) -> None:
    # platform budget 600, warn at 80% -> 480
    result = cost_module.evaluate_row(
        usage_row(month_to_date_cost_usd=500.0), cost_policies
    )
    assert result["decision"] == "warn"


def test_budget_exceeded_blocks(cost_module: ModuleType, cost_policies: dict) -> None:
    result = cost_module.evaluate_row(
        usage_row(month_to_date_cost_usd=650.0), cost_policies
    )
    assert result["decision"] == "block"


def test_unapproved_model_blocks(cost_module: ModuleType, cost_policies: dict) -> None:
    result = cost_module.evaluate_row(
        usage_row(model="gpt-4.1-mini"), cost_policies
    )
    assert result["decision"] == "block"


def test_unknown_team_blocks(cost_module: ModuleType, cost_policies: dict) -> None:
    result = cost_module.evaluate_row(usage_row(team="ghost"), cost_policies)
    assert result["decision"] == "block"


def test_hourly_cost_over_hard_limit_blocks(
    cost_module: ModuleType, cost_policies: dict
) -> None:
    result = cost_module.evaluate_row(
        usage_row(cost_per_hour_usd=1.50), cost_policies
    )
    assert result["decision"] == "block"
