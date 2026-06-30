#!/usr/bin/env python3
"""Score AI platform requests by governance risk."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

REQUIRED_REQUEST_COLUMNS = {
    "id",
    "team",
    "owner",
    "environment",
    "namespace",
    "action",
    "model",
    "provider",
    "input_tokens",
    "output_tokens",
    "forecast_monthly_cost_usd",
    "sensitive_data",
    "tool_access",
    "write_permission",
}

DEPLOY_ACTIONS = {
    "deploy_model",
    "enable_external_model",
    "scale_replicas",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate AI request risk scores.")
    parser.add_argument(
        "--requests",
        type=Path,
        default=Path(__file__).with_name("sample_requests.csv"),
        help="CSV request signal file.",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=Path(__file__).with_name("rules.yaml"),
        help="YAML rule file using the repository risk scoring format.",
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


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0", ""}:
        return False
    raise ValueError(f"unsupported boolean value: {value}")


def parse_rules(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"rules file does not exist: {path}")

    rules: dict[str, Any] = {
        "score_weights": {},
        "thresholds": {},
        "external_providers": [],
        "production_namespaces": [],
    }
    section: str | None = None

    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0:
            section = line.rstrip(":")
            if section not in rules:
                raise ValueError(f"unsupported rule section: {section}")
            continue

        if section in {"score_weights", "thresholds"} and indent == 2:
            key, _, value = line.partition(":")
            if not key or not value:
                raise ValueError(f"unsupported rule entry: {raw_line}")
            rules[section][key] = parse_scalar(value)
            continue

        if section in {"external_providers", "production_namespaces"} and indent == 2:
            if not line.startswith("- "):
                raise ValueError(f"unsupported rule list item: {raw_line}")
            rules[section].append(line[2:])
            continue

        raise ValueError(f"unsupported rule format line: {raw_line}")

    return rules


def load_requests(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"request file does not exist: {path}")

    rows: list[dict[str, Any]] = []
    with path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        missing = REQUIRED_REQUEST_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")

        for row in reader:
            rows.append(
                {
                    **row,
                    "input_tokens": int(row["input_tokens"]),
                    "output_tokens": int(row["output_tokens"]),
                    "forecast_monthly_cost_usd": float(row["forecast_monthly_cost_usd"]),
                    "sensitive_data": parse_bool(row["sensitive_data"]),
                    "tool_access": parse_bool(row["tool_access"]),
                    "write_permission": parse_bool(row["write_permission"]),
                }
            )

    return rows


def risk_level(score: int, thresholds: dict[str, Any]) -> str:
    if score >= int(thresholds["critical_min"]):
        return "critical"
    if score >= int(thresholds["high_min"]):
        return "high"
    if score >= int(thresholds["medium_min"]):
        return "medium"
    return "low"


def evaluate_request(
    request: dict[str, Any],
    rules: dict[str, Any],
    registry: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    weights = rules["score_weights"]
    thresholds = rules["thresholds"]
    score = 0
    factors: list[dict[str, Any]] = []

    def add_factor(name: str, points: int, reason: str) -> None:
        nonlocal score
        score += points
        factors.append({"name": name, "points": points, "reason": reason})

    if not request["owner"]:
        add_factor(
            "missing_owner",
            int(weights["missing_owner"]),
            "request has no responsible owner",
        )

    if request["provider"] in set(rules["external_providers"]):
        add_factor(
            "external_provider",
            int(weights["external_provider"]),
            f"provider {request['provider']} is external",
        )

    if (
        request["environment"] == "production"
        or request["namespace"] in set(rules["production_namespaces"])
        or request["namespace"].endswith("-prod")
    ):
        add_factor(
            "production_namespace",
            int(weights["production_namespace"]),
            f"namespace {request['namespace']} is production-facing",
        )

    token_volume = request["input_tokens"] + request["output_tokens"]
    if token_volume >= int(thresholds["high_token_volume"]):
        add_factor(
            "high_token_volume",
            int(weights["high_token_volume"]),
            f"token volume {token_volume} exceeds threshold",
        )

    if request["forecast_monthly_cost_usd"] >= float(
        thresholds["high_cost_forecast_usd"]
    ):
        add_factor(
            "high_cost_forecast",
            int(weights["high_cost_forecast"]),
            "forecasted monthly cost exceeds threshold",
        )

    if request["sensitive_data"]:
        add_factor(
            "sensitive_data",
            int(weights["sensitive_data"]),
            "request may process sensitive data",
        )

    if request["tool_access"]:
        add_factor(
            "tool_access",
            int(weights["tool_access"]),
            "request enables tool access",
        )

    if request["write_permission"]:
        add_factor(
            "write_permission",
            int(weights["write_permission"]),
            "request grants write permission",
        )

    if request["action"] in DEPLOY_ACTIONS:
        add_factor(
            "deploy_permission",
            int(weights["deploy_permission"]),
            f"action {request['action']} can change serving state",
        )

    if registry is not None:
        entry = registry.get(request["model"])
        if entry is None:
            add_factor(
                "unregistered_model",
                int(weights.get("missing_owner", 10)),
                f"model {request['model']} is not in the risk registry",
            )
        else:
            tier = entry.get("risk_tier")
            if tier == "critical":
                add_factor(
                    "registry_critical_tier",
                    int(weights.get("high_cost_forecast", 20)),
                    f"model {request['model']} is tagged critical in the registry",
                )
            elif tier == "high":
                add_factor(
                    "registry_high_tier",
                    int(weights.get("external_provider", 15)),
                    f"model {request['model']} is tagged high risk in the registry",
                )
            if request["sensitive_data"] and not entry.get("pii_allowed", False):
                add_factor(
                    "registry_pii_denied",
                    int(weights["sensitive_data"]),
                    f"model {request['model']} does not allow sensitive data",
                )

    bounded_score = min(score, 100)

    return {
        "id": request["id"],
        "team": request["team"],
        "owner": request["owner"] or None,
        "environment": request["environment"],
        "namespace": request["namespace"],
        "action": request["action"],
        "model": request["model"],
        "provider": request["provider"],
        "score": bounded_score,
        "level": risk_level(bounded_score, thresholds),
        "factors": factors,
        "signals": {
            "input_tokens": request["input_tokens"],
            "output_tokens": request["output_tokens"],
            "forecast_monthly_cost_usd": request["forecast_monthly_cost_usd"],
            "sensitive_data": request["sensitive_data"],
            "tool_access": request["tool_access"],
            "write_permission": request["write_permission"],
        },
    }


def build_result(request_path: Path, rule_path: Path) -> dict[str, Any]:
    rules = parse_rules(rule_path)
    requests = load_requests(request_path)
    scores = [evaluate_request(request, rules) for request in requests]
    level_counts = {
        level: sum(1 for item in scores if item["level"] == level)
        for level in ("low", "medium", "high", "critical")
    }

    return {
        "request_source": str(request_path),
        "rule_source": str(rule_path),
        "score_range": "0-100",
        "level_counts": level_counts,
        "risk_scores": scores,
    }


def main() -> int:
    args = parse_args()
    result = build_result(args.requests, args.rules)
    encoded = json.dumps(result, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{encoded}\n")
    else:
        print(encoded)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
