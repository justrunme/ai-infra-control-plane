"""Unit tests for tenant quota governance."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]


def quota_request(**overrides) -> dict:
    request = {
        "team": "platform",
        "input_tokens": 1000,
        "output_tokens": 500,
        "cost_per_request_usd": 0.01,
        "month_to_date_cost_usd": 100,
        "requests_last_minute": 1,
        "tokens_today": 1000,
        "sensitive_data": False,
    }
    request.update(overrides)
    return request


def test_quota_allows_within_limits(quota_module: ModuleType) -> None:
    policies = quota_module.parse_policies(REPO_ROOT / "governance/quota/policies.yaml")
    result = quota_module.evaluate_request(quota_request(), policies)
    assert result["decision"] == "allow"


def test_quota_blocks_on_rpm(quota_module: ModuleType) -> None:
    policies = quota_module.parse_policies(REPO_ROOT / "governance/quota/policies.yaml")
    result = quota_module.evaluate_request(
        quota_request(requests_last_minute=120), policies
    )
    assert result["decision"] == "block"


def test_quota_blocks_sensitive_data_for_finance(quota_module: ModuleType) -> None:
    policies = quota_module.parse_policies(REPO_ROOT / "governance/quota/policies.yaml")
    result = quota_module.evaluate_request(
        quota_request(team="finance", sensitive_data=True), policies
    )
    assert result["decision"] == "block"
