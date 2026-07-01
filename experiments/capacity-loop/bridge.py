#!/usr/bin/env python3
"""Bridge forecast recommendations into KEDA / HPA scaling hints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert capacity forecast output into scaling hints."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="JSON output from experiments/inference-autoscaling/simulate.py",
    )
    parser.add_argument(
        "--target-deployment",
        default="vllm-runtime",
        help="Kubernetes deployment or ScaledObject target name.",
    )
    parser.add_argument(
        "--prometheus-metric",
        default="vllm:num_requests_waiting",
        help="Queue pressure metric used by KEDA.",
    )
    parser.add_argument(
        "--threshold-per-replica",
        type=float,
        default=4.0,
        help="Target queue depth per replica for KEDA threshold math.",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path.")
    return parser.parse_args()


def load_forecast(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"forecast file does not exist: {path}")
    return json.loads(path.read_text())


def build_keda_hint(
    forecast: dict[str, Any],
    *,
    target_deployment: str,
    prometheus_metric: str,
    threshold_per_replica: float,
) -> dict[str, Any]:
    recommendation = forecast["recommendation"]
    recommended = int(recommendation["recommended_replicas"])
    current = int(recommendation["current_replicas"])
    peak_rps = float(recommendation["peak_forecast_rps"])
    peak_latency = float(recommendation["peak_forecast_p95_latency_ms"])
    scale_delta = int(recommendation["scale_delta"])

    action = "hold"
    if scale_delta > 0:
        action = "scale_up"
    elif scale_delta < 0:
        action = "scale_down"

    threshold = max(1.0, round(peak_rps / max(recommended, 1) / threshold_per_replica, 2))

    return {
        "action": action,
        "target_deployment": target_deployment,
        "current_replicas": current,
        "recommended_replicas": recommended,
        "scale_delta": scale_delta,
        "peak_forecast_rps": peak_rps,
        "peak_forecast_p95_latency_ms": peak_latency,
        "reasons": recommendation["reasons"],
        "keda": {
            "metric": prometheus_metric,
            "threshold": threshold,
            "minReplicaCount": max(1, current),
            "maxReplicaCount": max(recommended, current + 2),
        },
        "hpa_hint": {
            "minReplicas": max(1, current),
            "maxReplicas": max(recommended, current + 2),
            "target_cpu_utilization_percentage": 70,
        },
    }


def main() -> int:
    args = parse_args()
    forecast = load_forecast(args.input)
    result = build_keda_hint(
        forecast,
        target_deployment=args.target_deployment,
        prometheus_metric=args.prometheus_metric,
        threshold_per_replica=args.threshold_per_replica,
    )
    encoded = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{encoded}\n")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
