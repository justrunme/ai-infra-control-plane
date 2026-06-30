#!/usr/bin/env python3
"""Recommend inference replicas from forecasted load, latency, and token pressure."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections.abc import Iterable
from pathlib import Path
from statistics import mean

FORECAST_METRICS = (
    "request_rate_rps",
    "p95_latency_ms",
    "input_tokens_per_second",
    "output_tokens_per_second",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulate forecast-driven autoscaling for private AI inference."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).with_name("sample_load.csv"),
        help="CSV file with inference load signals.",
    )
    parser.add_argument(
        "--horizon", type=int, default=6, help="Forecast horizon in points."
    )
    parser.add_argument(
        "--target-utilization",
        type=float,
        default=0.70,
        help="Target request utilization per replica.",
    )
    parser.add_argument(
        "--latency-slo-ms",
        type=float,
        default=450.0,
        help="p95 latency SLO used for pressure-based scaling.",
    )
    parser.add_argument(
        "--token-capacity-per-replica",
        type=float,
        default=1800.0,
        help="Combined input and output token throughput capacity per replica.",
    )
    parser.add_argument(
        "--max-scale-up-step",
        type=int,
        default=2,
        help="Maximum replicas to add in one recommendation.",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output file.")
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, float | str]]:
    if not path.exists():
        raise FileNotFoundError(f"input file does not exist: {path}")

    rows: list[dict[str, float | str]] = []
    with path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        required = {
            "timestamp",
            "request_rate_rps",
            "p95_latency_ms",
            "input_tokens_per_second",
            "output_tokens_per_second",
            "current_replicas",
            "capacity_per_replica_rps",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")

        for row in reader:
            parsed: dict[str, float | str] = {"timestamp": row["timestamp"]}
            for key in required - {"timestamp"}:
                parsed[key] = float(row[key])
            rows.append(parsed)

    if len(rows) < 6:
        raise ValueError("at least six historical points are required")

    return rows


def series(rows: Iterable[dict[str, float | str]], metric: str) -> list[float]:
    return [float(row[metric]) for row in rows]


def trend_forecast(values: list[float], horizon: int, window: int = 6) -> list[float]:
    if horizon < 1:
        raise ValueError("horizon must be greater than zero")

    recent = values[-min(window, len(values)) :]
    slope = 0.0 if len(recent) < 2 else (recent[-1] - recent[0]) / (len(recent) - 1)
    baseline = mean(recent[-3:])
    return [round(max(0.0, baseline + slope * step), 4) for step in range(1, horizon + 1)]


def recommend_replicas(
    rows: list[dict[str, float | str]],
    forecasts: dict[str, list[float]],
    target_utilization: float,
    latency_slo_ms: float,
    token_capacity_per_replica: float,
    max_scale_up_step: int,
) -> dict[str, float | int | str | list[str]]:
    latest = rows[-1]
    current_replicas = int(float(latest["current_replicas"]))
    capacity_per_replica = float(latest["capacity_per_replica_rps"])

    peak_rps = max(forecasts["request_rate_rps"])
    peak_latency = max(forecasts["p95_latency_ms"])
    peak_tokens = max(
        input_tokens + output_tokens
        for input_tokens, output_tokens in zip(
            forecasts["input_tokens_per_second"],
            forecasts["output_tokens_per_second"],
            strict=True,
        )
    )

    request_replicas = math.ceil(peak_rps / (capacity_per_replica * target_utilization))
    latency_replicas = math.ceil(current_replicas * (peak_latency / latency_slo_ms))
    token_replicas = math.ceil(
        peak_tokens / (token_capacity_per_replica * target_utilization)
    )

    unconstrained = max(
        current_replicas, request_replicas, latency_replicas, token_replicas
    )
    recommended = min(unconstrained, current_replicas + max_scale_up_step)

    reasons = []
    if request_replicas > current_replicas:
        reasons.append("forecasted request load exceeds target utilization")
    if latency_replicas > current_replicas:
        reasons.append("forecasted p95 latency exceeds latency SLO")
    if token_replicas > current_replicas:
        reasons.append("forecasted token throughput exceeds target utilization")
    if unconstrained > recommended:
        reasons.append("recommendation capped by max scale-up step")
    if not reasons:
        reasons.append("current capacity is sufficient for the forecast horizon")

    return {
        "current_replicas": current_replicas,
        "recommended_replicas": recommended,
        "unconstrained_replicas": unconstrained,
        "current_capacity_rps": round(current_replicas * capacity_per_replica, 4),
        "target_capacity_rps": round(recommended * capacity_per_replica, 4),
        "peak_forecast_rps": round(peak_rps, 4),
        "peak_forecast_p95_latency_ms": round(peak_latency, 4),
        "peak_forecast_tokens_per_second": round(peak_tokens, 4),
        "scale_delta": recommended - current_replicas,
        "reasons": reasons,
    }


def build_result(args: argparse.Namespace) -> dict[str, object]:
    rows = load_rows(args.input)
    forecasts = {
        metric: trend_forecast(series(rows, metric), args.horizon)
        for metric in FORECAST_METRICS
    }
    recommendation = recommend_replicas(
        rows=rows,
        forecasts=forecasts,
        target_utilization=args.target_utilization,
        latency_slo_ms=args.latency_slo_ms,
        token_capacity_per_replica=args.token_capacity_per_replica,
        max_scale_up_step=args.max_scale_up_step,
    )

    return {
        "source": str(args.input),
        "history_points": len(rows),
        "horizon": args.horizon,
        "forecast_method": "rolling_trend_baseline",
        "inputs": {
            "target_utilization": args.target_utilization,
            "latency_slo_ms": args.latency_slo_ms,
            "token_capacity_per_replica": args.token_capacity_per_replica,
            "max_scale_up_step": args.max_scale_up_step,
        },
        "forecasts": forecasts,
        "recommendation": recommendation,
    }


def main() -> int:
    args = parse_args()
    result = build_result(args)
    encoded = json.dumps(result, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{encoded}\n")
    else:
        print(encoded)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
