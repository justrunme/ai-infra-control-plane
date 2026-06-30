#!/usr/bin/env python3
"""Evaluate tenant workload quotas before cost and risk governance."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def parse_scalar(value: str) -> Any:
    normalized = value.strip()
    if normalized == "":
        return ""
    if normalized.lower() in {"true", "yes"}:
        return True
    if normalized.lower() in {"false", "no"}:
        return False
    try:
        if "." in normalized:
            return float(normalized)
        return int(normalized)
    except ValueError:
        return normalized


def parse_policies(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"quota policy file does not exist: {path}")

    policies: dict[str, dict[str, Any]] = {}
    section: str | None = None
    current_tenant: str | None = None

    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0 and line == "tenants:":
            section = "tenants"
            continue

        if section != "tenants":
            raise ValueError(f"unsupported quota policy line: {raw_line}")

        if indent == 2 and line.endswith(":"):
            current_tenant = line[:-1]
            policies[current_tenant] = {}
            continue

        if indent == 4 and current_tenant is not None:
            key, _, value = line.partition(":")
            if not key or not value:
                raise ValueError(f"unsupported quota entry: {raw_line}")
            policies[current_tenant][key] = parse_scalar(value)
            continue

        raise ValueError(f"unsupported quota policy line: {raw_line}")

    return policies


def evaluate_request(
    request: dict[str, Any], policies: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    team = request["team"]
    tenant = policies.get(team)
    if tenant is None:
        return {
            "decision": "block",
            "reasons": [f"team {team} is not onboarded for tenant quotas"],
        }

    reasons: list[str] = []
    requests_last_minute = int(request.get("requests_last_minute", 0))
    tokens_today = int(request.get("tokens_today", 0))
    request_tokens = int(request.get("input_tokens", 0)) + int(
        request.get("output_tokens", 0)
    )

    rpm_limit = int(tenant.get("requests_per_minute", 0))
    if rpm_limit and requests_last_minute >= rpm_limit:
        reasons.append(
            f"team {team} exceeded requests_per_minute ({requests_last_minute}/{rpm_limit})"
        )

    token_limit = int(tenant.get("tokens_per_day", 0))
    projected_tokens = tokens_today + request_tokens
    if token_limit and projected_tokens > token_limit:
        reasons.append(
            f"team {team} would exceed tokens_per_day ({projected_tokens}/{token_limit})"
        )

    budget = tenant.get("max_monthly_budget_usd")
    month_to_date = float(request.get("month_to_date_cost_usd", 0))
    request_cost = float(request.get("cost_per_request_usd", 0))
    if budget is not None and month_to_date + request_cost > float(budget):
        reasons.append(
            f"team {team} would exceed max_monthly_budget_usd ({month_to_date + request_cost}/{budget})"
        )

    if request.get("sensitive_data") and not tenant.get("sensitive_data_allowed", False):
        reasons.append(f"team {team} is not allowed to process sensitive data")

    if reasons:
        return {"decision": "block", "reasons": reasons}

    return {"decision": "allow", "reasons": ["tenant quota checks passed"]}
