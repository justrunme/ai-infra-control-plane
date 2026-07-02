"""Tests for FinOps recommendation generation."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ANALYZE_PATH = Path(__file__).resolve().parents[1] / "analyze.py"
COST_PATH = REPO_ROOT / "governance/cost/evaluate.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_analyze_finops_finds_idle_and_budget_recommendations() -> None:
    finops_module = load_module("finops_recommendations", ANALYZE_PATH)
    cost_module = load_module("cost_governance", COST_PATH)
    usage_rows = finops_module.load_usage(
        REPO_ROOT / "governance/cost/sample_usage.csv"
    )
    policies = cost_module.parse_policy_file(
        REPO_ROOT / "governance/cost/policies.yaml"
    )
    utilization = finops_module.parse_utilization(
        REPO_ROOT / "finops/utilization.yaml"
    )

    recommendations = finops_module.analyze_finops(
        usage_rows, policies, utilization
    )

    categories = {item["category"] for item in recommendations}
    assert "idle_capacity" in categories
    assert "budget_pressure" in categories
    assert "route_local" in categories
    assert recommendations[0]["severity"] == "high"


def test_build_result_includes_savings_total() -> None:
    finops_module = load_module("finops_recommendations", ANALYZE_PATH)
    cost_module = load_module("cost_governance", COST_PATH)
    result = finops_module.build_result(
        REPO_ROOT / "governance/cost/sample_usage.csv",
        REPO_ROOT / "governance/cost/policies.yaml",
        REPO_ROOT / "finops/utilization.yaml",
        cost_module=cost_module,
    )

    assert result["recommendation_count"] >= 3
    assert result["estimated_monthly_savings_usd"] > 0
