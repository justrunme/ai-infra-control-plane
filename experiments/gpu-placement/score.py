#!/usr/bin/env python3
"""Score GPU placement options for private LLM inference workloads."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = {
    "workload_id",
    "model_size_gb",
    "batch_size",
    "queue_depth",
    "gpu_name",
    "gpu_vram_gb",
    "gpu_utilization",
    "cost_per_hour_usd",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score GPU placement for AI workloads.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).with_name("sample_workloads.csv"),
        help="CSV with workload and GPU candidate rows.",
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
                    "workload_id": row["workload_id"],
                    "model_size_gb": float(row["model_size_gb"]),
                    "batch_size": int(row["batch_size"]),
                    "queue_depth": int(row["queue_depth"]),
                    "gpu_name": row["gpu_name"],
                    "gpu_vram_gb": float(row["gpu_vram_gb"]),
                    "gpu_utilization": float(row["gpu_utilization"]),
                    "cost_per_hour_usd": float(row["cost_per_hour_usd"]),
                }
            )
    return rows


def score_placement(row: dict[str, Any]) -> dict[str, Any]:
    vram_required = row["model_size_gb"] * 1.2 + row["batch_size"] * 0.05
    vram_fit = row["gpu_vram_gb"] / max(vram_required, 0.1)
    util_headroom = max(0.0, 1.0 - row["gpu_utilization"])
    queue_penalty = min(row["queue_depth"] / 20.0, 1.0)
    cost_penalty = 1.0 / max(row["cost_per_hour_usd"], 0.01)

    score = round(
        (0.45 * min(vram_fit, 1.5))
        + (0.30 * util_headroom)
        + (0.15 * (1.0 - queue_penalty))
        + (0.10 * min(cost_penalty, 1.0)),
        4,
    )
    fits = vram_required <= row["gpu_vram_gb"] * 0.9
    recommendation = "place" if fits and score >= 0.55 else "reject"
    reasons: list[str] = []
    if not fits:
        reasons.append(
            f"model needs {vram_required:.1f} GB VRAM, "
            f"gpu has {row['gpu_vram_gb']:.1f} GB"
        )
    if row["gpu_utilization"] > 0.85:
        reasons.append(f"gpu utilization already {row['gpu_utilization']:.0%}")
    if row["queue_depth"] > 10:
        reasons.append(f"queue depth {row['queue_depth']} indicates congestion")
    if not reasons:
        reasons.append("workload fits GPU capacity and utilization headroom")

    return {
        "workload_id": row["workload_id"],
        "gpu_name": row["gpu_name"],
        "score": score,
        "recommendation": recommendation,
        "reasons": reasons,
        "signals": {
            "vram_required_gb": round(vram_required, 2),
            "gpu_vram_gb": row["gpu_vram_gb"],
            "gpu_utilization": row["gpu_utilization"],
            "queue_depth": row["queue_depth"],
            "cost_per_hour_usd": row["cost_per_hour_usd"],
        },
    }


def build_result(path: Path) -> dict[str, Any]:
    rows = load_rows(path)
    placements = [score_placement(row) for row in rows]
    by_workload: dict[str, list[dict[str, Any]]] = {}
    for placement in placements:
        by_workload.setdefault(placement["workload_id"], []).append(placement)

    winners = []
    for _workload_id, options in by_workload.items():
        eligible = [item for item in options if item["recommendation"] == "place"]
        if eligible:
            winner = max(eligible, key=lambda item: item["score"])
        else:
            winner = max(options, key=lambda item: item["score"])
        winners.append(winner)

    return {
        "input_source": str(path),
        "placement_count": len(placements),
        "winners": winners,
        "placements": placements,
    }


def main() -> int:
    args = parse_args()
    result = build_result(args.input)
    encoded = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{encoded}\n")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
