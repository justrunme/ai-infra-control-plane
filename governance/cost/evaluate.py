#!/usr/bin/env python3
"""Evaluate AI usage against cost governance policies."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

REQUIRED_USAGE_COLUMNS = {
    "timestamp",
    "team",
    "model",
    "provider",
    "input_tokens",
    "output_tokens",
    "cost_per_request_usd",
    "cost_per_hour_usd",
    "month_to_date_cost_usd",
    "forecast_monthly_cost_usd",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate AI cost governance policies.")
    parser.add_argument(
        "--usage",
        type=Path,
        default=Path(__file__).with_name("sample_usage.csv"),
        help="CSV usage file.",
    )
    parser.add_argument(
        "--policies",
        type=Path,
        default=Path(__file__).with_name("policies.yaml"),
        help="YAML policy file using the repository cost governance format.",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path.")
    return parser.parse_args()


def parse_scalar(value: str) -> Any:
    normalized = value.strip()
    if normalized == "":
        return ""
    try:
        if "." in normalized:
            return float(normalized)
        return int(normalized)
    except ValueError:
        return normalized


def parse_policy_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"policy file does not exist: {path}")

    policies: dict[str, Any] = {"global": {}, "teams": {}}
    section: str | None = None
    current_team: str | None = None
    current_list_key: str | None = None

    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0:
            key, _, value = line.partition(":")
            if value.strip():
                policies[key] = parse_scalar(value)
                section = None
            else:
                section = key
            current_team = None
            current_list_key = None
            continue

        if section == "global" and indent == 2:
            key, _, value = line.partition(":")
            policies["global"][key] = parse_scalar(value)
            current_list_key = None
            continue

        if section == "teams" and indent == 2:
            current_team = line.rstrip(":")
            policies["teams"][current_team] = {}
            current_list_key = None
            continue

        if section == "teams" and indent == 4 and current_team:
            key, _, value = line.partition(":")
            if value.strip():
                policies["teams"][current_team][key] = parse_scalar(value)
                current_list_key = None
            else:
                policies["teams"][current_team][key] = []
                current_list_key = key
            continue

        if section == "teams" and indent == 6 and current_team and current_list_key:
            if not line.startswith("- "):
                raise ValueError(f"unsupported policy list item: {raw_line}")
            policies["teams"][current_team][current_list_key].append(line[2:])
            continue

        raise ValueError(f"unsupported policy format line: {raw_line}")

    return policies


def load_usage(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"usage file does not exist: {path}")

    rows: list[dict[str, Any]] = []
    with path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        missing = REQUIRED_USAGE_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")

        for row in reader:
            rows.append(
                {
                    **row,
                    "input_tokens": int(row["input_tokens"]),
                    "output_tokens": int(row["output_tokens"]),
                    "cost_per_request_usd": float(row["cost_per_request_usd"]),
                    "cost_per_hour_usd": float(row["cost_per_hour_usd"]),
                    "month_to_date_cost_usd": float(row["month_to_date_cost_usd"]),
                    "forecast_monthly_cost_usd": float(row["forecast_monthly_cost_usd"]),
                }
            )

    return rows


def evaluate_row(row: dict[str, Any], policies: dict[str, Any]) -> dict[str, Any]:
    global_policy = policies["global"]
    team_policy = policies["teams"].get(row["team"])
    reasons: list[str] = []
    warnings: list[str] = []

    if team_policy is None:
        reasons.append(f"team {row['team']} has no cost governance policy")
    else:
        allowed_models = set(team_policy.get("allowed_models", []))
        if row["model"] not in allowed_models:
            reasons.append(f"model {row['model']} is not approved for team {row['team']}")

        monthly_budget = float(team_policy["monthly_budget_usd"])
        warn_threshold = monthly_budget * (float(team_policy["warn_at_percent"]) / 100)
        if row["month_to_date_cost_usd"] > monthly_budget:
            reasons.append(f"team {row['team']} monthly budget exceeded")
        elif row["month_to_date_cost_usd"] >= warn_threshold:
            warnings.append(f"team {row['team']} is near monthly budget")

    if row["cost_per_hour_usd"] > float(global_policy["max_model_hourly_cost_usd"]):
        reasons.append("model hourly cost exceeds hard limit")
    elif row["cost_per_hour_usd"] >= float(global_policy["warn_model_hourly_cost_usd"]):
        warnings.append("model hourly cost is near hard limit")

    if row["forecast_monthly_cost_usd"] > float(
        global_policy["max_forecast_monthly_cost_usd"]
    ):
        reasons.append("forecasted monthly cost exceeds platform hard limit")
    elif row["forecast_monthly_cost_usd"] >= float(
        global_policy["warn_forecast_monthly_cost_usd"]
    ):
        warnings.append("forecasted monthly cost is near platform hard limit")

    if reasons:
        decision = "block"
        decision_reasons = reasons
    elif warnings:
        decision = "warn"
        decision_reasons = warnings
    else:
        decision = "allow"
        decision_reasons = ["usage is within governance limits"]

    return {
        "timestamp": row["timestamp"],
        "team": row["team"],
        "model": row["model"],
        "provider": row["provider"],
        "decision": decision,
        "reasons": decision_reasons,
        "usage": {
            "input_tokens": row["input_tokens"],
            "output_tokens": row["output_tokens"],
            "cost_per_request_usd": row["cost_per_request_usd"],
            "cost_per_hour_usd": row["cost_per_hour_usd"],
            "month_to_date_cost_usd": row["month_to_date_cost_usd"],
            "forecast_monthly_cost_usd": row["forecast_monthly_cost_usd"],
        },
    }


def build_result(usage_path: Path, policy_path: Path) -> dict[str, Any]:
    policies = parse_policy_file(policy_path)
    usage_rows = load_usage(usage_path)
    decisions = [evaluate_row(row, policies) for row in usage_rows]
    counts = {
        decision: sum(1 for item in decisions if item["decision"] == decision)
        for decision in ("allow", "warn", "block")
    }

    return {
        "usage_source": str(usage_path),
        "policy_source": str(policy_path),
        "currency": policies.get("currency", "USD"),
        "decision_counts": counts,
        "decisions": decisions,
    }


def main() -> int:
    args = parse_args()
    result = build_result(args.usage, args.policies)
    encoded = json.dumps(result, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{encoded}\n")
    else:
        print(encoded)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
