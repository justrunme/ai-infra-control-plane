#!/usr/bin/env python3
"""Emit OpenTelemetry GenAI-style spans and metrics from sample inference data."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = {
    "timestamp",
    "trace_id",
    "span_id",
    "team",
    "provider",
    "backend",
    "operation",
    "request_model",
    "response_model",
    "input_tokens",
    "output_tokens",
    "latency_ms",
    "tool_calls",
    "temperature",
    "max_tokens",
    "estimated_cost_usd",
    "finish_reason",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emit GenAI telemetry spans and aggregate metrics from sample data."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).with_name("sample_requests.csv"),
        help="CSV file containing sample GenAI request metadata.",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path.")
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"input file does not exist: {path}")

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
                    "latency_ms": float(row["latency_ms"]),
                    "tool_calls": int(row["tool_calls"]),
                    "temperature": float(row["temperature"]),
                    "max_tokens": int(row["max_tokens"]),
                    "estimated_cost_usd": float(row["estimated_cost_usd"]),
                }
            )

    return rows


def build_span(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": f"gen_ai.{row['operation']}",
        "trace_id": row["trace_id"],
        "span_id": row["span_id"],
        "start_time": row["timestamp"],
        "duration_ms": row["latency_ms"],
        "attributes": {
            "gen_ai.operation.name": row["operation"],
            "gen_ai.provider.name": row["provider"],
            "gen_ai.request.model": row["request_model"],
            "gen_ai.response.model": row["response_model"],
            "gen_ai.usage.input_tokens": row["input_tokens"],
            "gen_ai.usage.output_tokens": row["output_tokens"],
            "gen_ai.response.finish_reasons": [row["finish_reason"]],
            "gen_ai.request.temperature": row["temperature"],
            "gen_ai.request.max_tokens": row["max_tokens"],
            "ai_control.estimated_cost_usd": row["estimated_cost_usd"],
            "ai_control.team": row["team"],
            "ai_control.backend": row["backend"],
            "ai_control.tool_calls": row["tool_calls"],
        },
    }


def aggregate_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "tool_calls": 0,
            "estimated_cost_usd": 0.0,
            "latency_ms_total": 0.0,
        }
    )
    by_team_cost: dict[str, float] = defaultdict(float)

    for row in rows:
        model = row["response_model"]
        metrics = by_model[model]
        metrics["requests"] += 1
        metrics["input_tokens"] += row["input_tokens"]
        metrics["output_tokens"] += row["output_tokens"]
        metrics["tool_calls"] += row["tool_calls"]
        metrics["estimated_cost_usd"] += row["estimated_cost_usd"]
        metrics["latency_ms_total"] += row["latency_ms"]
        by_team_cost[row["team"]] += row["estimated_cost_usd"]

    model_metrics = {}
    for model, metrics in sorted(by_model.items()):
        requests = metrics["requests"]
        model_metrics[model] = {
            "requests": int(requests),
            "input_tokens": int(metrics["input_tokens"]),
            "output_tokens": int(metrics["output_tokens"]),
            "tool_calls": int(metrics["tool_calls"]),
            "estimated_cost_usd": round(metrics["estimated_cost_usd"], 6),
            "avg_latency_ms": round(metrics["latency_ms_total"] / requests, 4),
        }

    return {
        "requests_total": len(rows),
        "models": model_metrics,
        "team_cost_usd": {
            team: round(cost, 6) for team, cost in sorted(by_team_cost.items())
        },
        "estimated_cost_usd_total": round(
            sum(row["estimated_cost_usd"] for row in rows),
            6,
        ),
    }


def build_result(rows: list[dict[str, Any]], source: Path) -> dict[str, Any]:
    return {
        "source": str(source),
        "schema": "otel-genai-prototype",
        "span_count": len(rows),
        "spans": [build_span(row) for row in rows],
        "metrics": aggregate_metrics(rows),
    }


def main() -> int:
    args = parse_args()
    rows = load_rows(args.input)
    result = build_result(rows, args.input)
    encoded = json.dumps(result, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{encoded}\n")
    else:
        print(encoded)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
