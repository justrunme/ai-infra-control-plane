#!/usr/bin/env python3
"""Evaluate AI platform requests against approval workflow rules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_REQUEST_FIELDS = {
    "id",
    "team",
    "owner",
    "environment",
    "namespace",
    "action",
    "model",
    "provider",
    "cost_decision",
    "cost_per_hour_usd",
    "forecast_monthly_cost_usd",
    "risk",
}

FORBIDDEN_MODELS = {
    "unknown-frontier-model",
}

EXTERNAL_PROVIDERS = {
    "anthropic",
    "openai",
    "external",
}

HIGH_RISK_ACTIONS = {
    "deploy_model",
    "enable_external_model",
    "scale_replicas",
}

SUPPORTED_TEAMS = {
    "platform",
    "search",
    "mlops",
    "finance",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate AI approval workflow requests.")
    parser.add_argument(
        "--requests",
        type=Path,
        default=Path(__file__).with_name("requests.yaml"),
        help="YAML request file using the repository approval workflow format.",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path.")
    return parser.parse_args()


def parse_scalar(value: str) -> Any:
    normalized = value.strip()
    if normalized == "":
        return ""
    if normalized.lower() == "none":
        return None
    try:
        if "." in normalized:
            return float(normalized)
        return int(normalized)
    except ValueError:
        return normalized


def load_requests(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"request file does not exist: {path}")

    requests: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_requests = False

    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0 and line == "requests:":
            in_requests = True
            continue

        if not in_requests:
            raise ValueError(f"unsupported request format line: {raw_line}")

        if indent == 2 and line.startswith("- "):
            if current:
                requests.append(current)
            current = {}
            key, _, value = line[2:].partition(":")
            if not key or not value:
                raise ValueError(f"unsupported request list item: {raw_line}")
            current[key] = parse_scalar(value)
            continue

        if indent == 4 and current is not None:
            key, _, value = line.partition(":")
            if not key or not value:
                raise ValueError(f"unsupported request field: {raw_line}")
            current[key] = parse_scalar(value)
            continue

        raise ValueError(f"unsupported request format line: {raw_line}")

    if current:
        requests.append(current)

    for request in requests:
        missing = REQUIRED_REQUEST_FIELDS - set(request)
        if missing:
            request_id = request.get("id", "unknown")
            raise ValueError(
                f"request {request_id} is missing fields: {', '.join(sorted(missing))}"
            )

    return requests


def evaluate_request(request: dict[str, Any]) -> dict[str, Any]:
    block_reasons: list[str] = []
    approval_reasons: list[str] = []

    owner = request["owner"]
    if owner in (None, "", "none"):
        block_reasons.append("request has no responsible owner")

    if request["team"] not in SUPPORTED_TEAMS:
        block_reasons.append(f"team {request['team']} is not onboarded for AI governance")

    if request["model"] in FORBIDDEN_MODELS:
        block_reasons.append(f"model {request['model']} is forbidden")

    if request["cost_decision"] == "block":
        block_reasons.append("cost governance returned block")
    elif request["cost_decision"] == "warn":
        approval_reasons.append("cost governance returned warn")

    if request["environment"] == "production" or request["namespace"].endswith("-prod"):
        approval_reasons.append("production environment requires human approval")

    if request["provider"] in EXTERNAL_PROVIDERS:
        approval_reasons.append("external model provider requires human approval")

    if request["action"] in HIGH_RISK_ACTIONS:
        approval_reasons.append(f"action {request['action']} changes serving posture")

    if request["risk"] in {"high", "critical"}:
        approval_reasons.append(f"risk level is {request['risk']}")

    if float(request["cost_per_hour_usd"]) >= 0.75:
        approval_reasons.append("model hourly cost is above approval threshold")

    if float(request["forecast_monthly_cost_usd"]) >= 1500:
        approval_reasons.append("forecasted monthly cost is above approval threshold")

    if block_reasons:
        decision = "block"
        reasons = block_reasons
    elif approval_reasons:
        decision = "approval_required"
        reasons = approval_reasons
    else:
        decision = "allow"
        reasons = ["request is low-risk and inside approval limits"]

    return {
        "id": request["id"],
        "team": request["team"],
        "owner": request["owner"],
        "environment": request["environment"],
        "namespace": request["namespace"],
        "action": request["action"],
        "model": request["model"],
        "provider": request["provider"],
        "decision": decision,
        "reasons": reasons,
        "signals": {
            "cost_decision": request["cost_decision"],
            "cost_per_hour_usd": request["cost_per_hour_usd"],
            "forecast_monthly_cost_usd": request["forecast_monthly_cost_usd"],
            "risk": request["risk"],
        },
    }


def build_result(request_path: Path) -> dict[str, Any]:
    requests = load_requests(request_path)
    approvals = [evaluate_request(request) for request in requests]
    counts = {
        decision: sum(1 for item in approvals if item["decision"] == decision)
        for decision in ("allow", "approval_required", "block")
    }

    return {
        "request_source": str(request_path),
        "decision_counts": counts,
        "approvals": approvals,
    }


def main() -> int:
    args = parse_args()
    result = build_result(args.requests)
    encoded = json.dumps(result, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{encoded}\n")
    else:
        print(encoded)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
