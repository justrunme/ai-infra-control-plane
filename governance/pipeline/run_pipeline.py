#!/usr/bin/env python3
"""Run an end-to-end AI governance decision pipeline."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

REQUIRED_COLUMNS = {
    "id",
    "timestamp",
    "team",
    "owner",
    "environment",
    "namespace",
    "action",
    "model",
    "provider",
    "input_tokens",
    "output_tokens",
    "cost_per_request_usd",
    "cost_per_hour_usd",
    "month_to_date_cost_usd",
    "forecast_monthly_cost_usd",
    "sensitive_data",
    "tool_access",
    "write_permission",
}

REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_ROOT = REPO_ROOT / "governance"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AI governance pipeline.")
    parser.add_argument(
        "--requests",
        type=Path,
        default=Path(__file__).with_name("sample_requests.csv"),
        help="CSV request file.",
    )
    parser.add_argument(
        "--cost-policies",
        type=Path,
        default=GOVERNANCE_ROOT / "cost" / "policies.yaml",
        help="Cost governance policy file.",
    )
    parser.add_argument(
        "--risk-rules",
        type=Path,
        default=GOVERNANCE_ROOT / "risk" / "rules.yaml",
        help="Risk scoring rule file.",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path.")
    return parser.parse_args()


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0", ""}:
        return False
    raise ValueError(f"unsupported boolean value: {value}")


def load_requests(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"request file does not exist: {path}")

    rows: list[dict[str, Any]] = []
    with path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
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
                    "sensitive_data": parse_bool(row["sensitive_data"]),
                    "tool_access": parse_bool(row["tool_access"]),
                    "write_permission": parse_bool(row["write_permission"]),
                }
            )

    return rows


def build_approval_request(
    request: dict[str, Any],
    cost_decision: str,
    risk_level: str,
) -> dict[str, Any]:
    return {
        "id": request["id"],
        "team": request["team"],
        "owner": request["owner"] or None,
        "environment": request["environment"],
        "namespace": request["namespace"],
        "action": request["action"],
        "model": request["model"],
        "provider": request["provider"],
        "cost_decision": cost_decision,
        "cost_per_hour_usd": request["cost_per_hour_usd"],
        "forecast_monthly_cost_usd": request["forecast_monthly_cost_usd"],
        "risk": risk_level,
    }


def final_verdict(
    cost_result: dict[str, Any],
    risk_result: dict[str, Any],
    approval_result: dict[str, Any],
) -> tuple[str, list[str]]:
    if cost_result["decision"] == "block":
        return "block", ["cost governance blocked the request"]
    if approval_result["decision"] == "block":
        return "block", ["approval workflow blocked the request"]
    if risk_result["level"] == "critical":
        return "approval_required", ["critical risk score requires human approval"]
    if approval_result["decision"] == "approval_required":
        return "approval_required", ["approval workflow requires human review"]
    if cost_result["decision"] == "warn":
        return "approval_required", ["cost governance warning requires review"]
    return "allow", ["all governance stages allow the request"]


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def evaluate_pipeline(
    request_path: Path,
    cost_policy_path: Path,
    risk_rule_path: Path,
) -> dict[str, Any]:
    cost_module = load_module("cost_governance", GOVERNANCE_ROOT / "cost" / "evaluate.py")
    risk_module = load_module("risk_governance", GOVERNANCE_ROOT / "risk" / "evaluate.py")
    approval_module = load_module(
        "approval_governance",
        GOVERNANCE_ROOT / "approval" / "evaluate.py",
    )

    cost_policies = cost_module.parse_policy_file(cost_policy_path)
    risk_rules = risk_module.parse_rules(risk_rule_path)
    requests = load_requests(request_path)

    decisions = []
    for request in requests:
        cost_result = cost_module.evaluate_row(request, cost_policies)
        risk_result = risk_module.evaluate_request(request, risk_rules)
        approval_request = build_approval_request(
            request,
            cost_result["decision"],
            risk_result["level"],
        )
        approval_result = approval_module.evaluate_request(approval_request)
        verdict, reasons = final_verdict(cost_result, risk_result, approval_result)

        decisions.append(
            {
                "id": request["id"],
                "final_verdict": verdict,
                "reasons": reasons,
                "request": {
                    "team": request["team"],
                    "owner": request["owner"] or None,
                    "environment": request["environment"],
                    "namespace": request["namespace"],
                    "action": request["action"],
                    "model": request["model"],
                    "provider": request["provider"],
                },
                "telemetry": {
                    "input_tokens": request["input_tokens"],
                    "output_tokens": request["output_tokens"],
                    "cost_per_request_usd": request["cost_per_request_usd"],
                    "cost_per_hour_usd": request["cost_per_hour_usd"],
                    "month_to_date_cost_usd": request["month_to_date_cost_usd"],
                    "forecast_monthly_cost_usd": request["forecast_monthly_cost_usd"],
                    "sensitive_data": request["sensitive_data"],
                    "tool_access": request["tool_access"],
                    "write_permission": request["write_permission"],
                },
                "stages": {
                    "cost": {
                        "decision": cost_result["decision"],
                        "reasons": cost_result["reasons"],
                    },
                    "risk": {
                        "score": risk_result["score"],
                        "level": risk_result["level"],
                        "factors": risk_result["factors"],
                    },
                    "approval": {
                        "decision": approval_result["decision"],
                        "reasons": approval_result["reasons"],
                    },
                },
            }
        )

    verdict_counts = {
        verdict: sum(1 for item in decisions if item["final_verdict"] == verdict)
        for verdict in ("allow", "approval_required", "block")
    }

    return {
        "request_source": repo_relative(request_path),
        "cost_policy_source": repo_relative(cost_policy_path),
        "risk_rule_source": repo_relative(risk_rule_path),
        "flow": [
            "request",
            "telemetry_sample",
            "cost_decision",
            "risk_score",
            "approval_decision",
            "final_verdict",
        ],
        "verdict_counts": verdict_counts,
        "decisions": decisions,
    }


def main() -> int:
    args = parse_args()
    result = evaluate_pipeline(args.requests, args.cost_policies, args.risk_rules)
    encoded = json.dumps(result, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{encoded}\n")
    else:
        print(encoded)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
