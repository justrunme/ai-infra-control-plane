#!/usr/bin/env python3
"""Generate FinOps recommendations from usage, budgets, and utilization signals."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any
from uuid import uuid4

LOCAL_PROVIDERS = {"ollama", "vllm", "local"}
EXTERNAL_PROVIDERS = {"openai", "anthropic", "external"}


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


def parse_utilization(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"utilization file does not exist: {path}")

    config: dict[str, Any] = {
        "models": {},
        "idle_utilization_threshold": 0.15,
        "idle_requests_per_day_threshold": 50,
    }
    section: str | None = None
    current_model: str | None = None

    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0:
            key, _, value = line.partition(":")
            if value.strip():
                config[key] = parse_scalar(value)
                section = None
                continue
            if key == "models":
                section = "models"
                continue
            raise ValueError(f"unsupported utilization line: {raw_line}")

        if section == "models":
            if indent == 2 and line.endswith(":"):
                current_model = line[:-1]
                config["models"][current_model] = {}
                continue
            if indent == 4 and current_model is not None:
                key, _, value = line.partition(":")
                if not key or not value:
                    raise ValueError(f"unsupported utilization entry: {raw_line}")
                config["models"][current_model][key] = parse_scalar(value)
                continue

        raise ValueError(f"unsupported utilization line: {raw_line}")

    return config


def load_usage(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"usage file does not exist: {path}")

    with path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return [
            {
                "timestamp": row["timestamp"],
                "team": row["team"],
                "model": row["model"],
                "provider": row["provider"],
                "input_tokens": int(row["input_tokens"]),
                "output_tokens": int(row["output_tokens"]),
                "cost_per_request_usd": float(row["cost_per_request_usd"]),
                "cost_per_hour_usd": float(row["cost_per_hour_usd"]),
                "month_to_date_cost_usd": float(row["month_to_date_cost_usd"]),
                "forecast_monthly_cost_usd": float(row["forecast_monthly_cost_usd"]),
            }
            for row in reader
        ]


def aggregate_usage(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    aggregated: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["team"], row["model"])
        current = aggregated.setdefault(
            key,
            {
                "team": row["team"],
                "model": row["model"],
                "provider": row["provider"],
                "max_forecast_monthly_cost_usd": 0.0,
                "max_month_to_date_cost_usd": 0.0,
                "max_cost_per_hour_usd": 0.0,
                "total_tokens": 0,
            },
        )
        current["provider"] = row["provider"]
        current["max_forecast_monthly_cost_usd"] = max(
            current["max_forecast_monthly_cost_usd"],
            row["forecast_monthly_cost_usd"],
        )
        current["max_month_to_date_cost_usd"] = max(
            current["max_month_to_date_cost_usd"],
            row["month_to_date_cost_usd"],
        )
        current["max_cost_per_hour_usd"] = max(
            current["max_cost_per_hour_usd"],
            row["cost_per_hour_usd"],
        )
        current["total_tokens"] += row["input_tokens"] + row["output_tokens"]
    return aggregated


def recommendation(
    *,
    category: str,
    severity: str,
    team: str,
    model: str,
    title: str,
    summary: str,
    estimated_monthly_savings_usd: float,
    actions: list[str],
) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "category": category,
        "severity": severity,
        "team": team,
        "model": model,
        "title": title,
        "summary": summary,
        "estimated_monthly_savings_usd": round(estimated_monthly_savings_usd, 2),
        "actions": actions,
    }


def local_alternative(team: str, policies: dict[str, Any]) -> str | None:
    team_policy = policies.get("teams", {}).get(team, {})
    allowed = team_policy.get("allowed_models", [])
    for model in allowed:
        if isinstance(model, str) and "llama" in model.lower():
            return model
    if allowed:
        return str(allowed[0])
    return None


def analyze_finops(
    usage_rows: list[dict[str, Any]],
    policies: dict[str, Any],
    utilization_config: dict[str, Any],
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    aggregated = aggregate_usage(usage_rows)
    utilization_models = utilization_config.get("models", {})
    idle_util_threshold = float(
        utilization_config.get("idle_utilization_threshold", 0.15)
    )
    idle_rpd_threshold = int(
        utilization_config.get("idle_requests_per_day_threshold", 50)
    )

    for (team, model), stats in aggregated.items():
        team_policy = policies.get("teams", {}).get(team, {})
        monthly_budget = float(team_policy.get("monthly_budget_usd", 0))
        warn_percent = float(team_policy.get("warn_at_percent", 80))
        forecast = float(stats["max_forecast_monthly_cost_usd"])
        hourly_cost = float(stats["max_cost_per_hour_usd"])
        provider = str(stats["provider"])

        if monthly_budget and forecast >= monthly_budget * warn_percent / 100:
            overage = max(0.0, forecast - monthly_budget * warn_percent / 100)
            recommendations.append(
                recommendation(
                    category="budget_pressure",
                    severity="high" if forecast >= monthly_budget else "medium",
                    team=team,
                    model=model,
                    title=f"Review {team} budget for {model}",
                    summary=(
                        f"Forecast monthly spend ${forecast:.2f} is at or above "
                        f"{warn_percent:.0f}% of the ${monthly_budget:.2f} team budget."
                    ),
                    estimated_monthly_savings_usd=overage,
                    actions=[
                        "tighten tenant quota for the team",
                        "shift traffic to a lower-cost local model",
                        "require approval for external providers",
                    ],
                )
            )

        if provider in EXTERNAL_PROVIDERS:
            alternative = local_alternative(team, policies)
            if alternative and alternative != model:
                savings = max(forecast * 0.35, hourly_cost * 24 * 30 * 0.35)
                recommendations.append(
                    recommendation(
                        category="route_local",
                        severity="medium",
                        team=team,
                        model=model,
                        title=f"Route {team} traffic from {model} to {alternative}",
                        summary=(
                            f"External provider {provider} drives higher forecast spend. "
                            f"A local allowed model ({alternative}) can serve "
                            "part of the workload."
                        ),
                        estimated_monthly_savings_usd=savings,
                        actions=[
                            f"enable gateway routing policy preferring {alternative}",
                            "run shadow comparison for quality regression",
                            "update chargeback dashboard after cutover",
                        ],
                    )
                )

        util = utilization_models.get(model)
        if util is not None:
            gpu_util = float(util.get("gpu_utilization", 1.0))
            requests_per_day = int(util.get("requests_per_day", 0))
            replicas = int(util.get("replicas", 1))
            if gpu_util < idle_util_threshold and requests_per_day < idle_rpd_threshold:
                savings = hourly_cost * 24 * 30 * max(replicas - 1, 1) * 0.6
                recommendations.append(
                    recommendation(
                        category="idle_capacity",
                        severity="high",
                        team=team,
                        model=model,
                        title=f"Scale down idle capacity for {model}",
                        summary=(
                            f"GPU utilization {gpu_util:.0%} and {requests_per_day} "
                            "requests/day indicate over-provisioned replicas "
                            f"({replicas})."
                        ),
                        estimated_monthly_savings_usd=savings,
                        actions=[
                            "scale deployment replicas down during off-peak windows",
                            "move model to CPU-backed Ollama for bursty dev traffic",
                            "apply KEDA scale-to-zero if queue depth stays near zero",
                        ],
                    )
                )

    severity_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(
        key=lambda item: (
            severity_order.get(item["severity"], 9),
            -item["estimated_monthly_savings_usd"],
        )
    )
    return recommendations


def build_result(
    usage_path: Path,
    policy_path: Path,
    utilization_path: Path,
    *,
    cost_module: Any,
) -> dict[str, Any]:
    policies = cost_module.parse_policy_file(policy_path)
    usage_rows = load_usage(usage_path)
    utilization_config = parse_utilization(utilization_path)
    recommendations = analyze_finops(usage_rows, policies, utilization_config)
    savings = sum(item["estimated_monthly_savings_usd"] for item in recommendations)

    return {
        "currency": policies.get("currency", "USD"),
        "usage_source": str(usage_path),
        "policy_source": str(policy_path),
        "utilization_source": str(utilization_path),
        "recommendation_count": len(recommendations),
        "estimated_monthly_savings_usd": round(savings, 2),
        "recommendations": recommendations,
    }
