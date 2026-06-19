#!/usr/bin/env python3
"""Forecast private AI platform metrics with TimesFM or a lightweight fallback."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable

METRICS = (
    "request_latency_ms",
    "request_rate_rps",
    "capacity_available",
    "estimated_hourly_cost_usd",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Forecast AI infrastructure metrics from a CSV time series."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).with_name("sample_metrics.csv"),
        help="CSV file with a timestamp column and metric columns.",
    )
    parser.add_argument(
        "--metric",
        choices=METRICS,
        default="request_latency_ms",
        help="Metric column to forecast.",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=6,
        help="Number of future points to forecast.",
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "timesfm", "naive"),
        default="auto",
        help="Forecast backend. auto tries TimesFM and falls back to naive.",
    )
    return parser.parse_args()


def load_metric(path: Path, metric: str) -> list[float]:
    if not path.exists():
        raise FileNotFoundError(f"input file does not exist: {path}")

    values: list[float] = []
    with path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if metric not in (reader.fieldnames or []):
            raise ValueError(f"metric column not found in CSV: {metric}")

        for row_number, row in enumerate(reader, start=2):
            raw_value = row.get(metric, "")
            try:
                values.append(float(raw_value))
            except ValueError as exc:
                raise ValueError(
                    f"invalid numeric value for {metric} on CSV row {row_number}: {raw_value}"
                ) from exc

    if len(values) < 4:
        raise ValueError("at least four historical points are required")

    return values


def naive_forecast(values: list[float], horizon: int) -> list[float]:
    recent = values[-min(6, len(values)) :]
    if len(recent) < 2:
        slope = 0.0
    else:
        slope = (recent[-1] - recent[0]) / (len(recent) - 1)

    current = values[-1]
    forecast = [current + slope * step for step in range(1, horizon + 1)]
    return [round(max(0.0, value), 4) for value in forecast]


def timesfm_forecast(values: list[float], horizon: int) -> list[float]:
    import numpy as np
    import timesfm
    import torch

    torch.set_float32_matmul_precision("high")

    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
        "google/timesfm-2.5-200m-pytorch"
    )
    model.compile(
        timesfm.ForecastConfig(
            max_context=max(32, min(1024, len(values))),
            max_horizon=max(16, horizon),
            normalize_inputs=True,
            use_continuous_quantile_head=True,
            force_flip_invariance=True,
            infer_is_positive=True,
            fix_quantile_crossing=True,
        )
    )

    point_forecast, _ = model.forecast(
        horizon=horizon,
        inputs=[np.asarray(values, dtype=np.float32)],
    )
    return [round(float(value), 4) for value in point_forecast[0]]


def forecast(values: list[float], horizon: int, backend: str) -> tuple[str, list[float]]:
    if horizon < 1:
        raise ValueError("horizon must be greater than zero")

    if backend == "naive":
        return "naive", naive_forecast(values, horizon)

    try:
        return "timesfm", timesfm_forecast(values, horizon)
    except Exception as exc:
        if backend == "timesfm":
            raise
        print(
            f"TimesFM backend unavailable, using naive fallback: {exc}",
            file=sys.stderr,
        )
        return "naive", naive_forecast(values, horizon)


def build_result(
    metric: str,
    values: Iterable[float],
    horizon: int,
    backend: str,
    forecast_values: list[float],
) -> dict[str, object]:
    history = list(values)
    return {
        "metric": metric,
        "history_points": len(history),
        "backend": backend,
        "horizon": horizon,
        "last_observed": history[-1],
        "forecast": forecast_values,
    }


def main() -> int:
    args = parse_args()
    try:
        values = load_metric(args.input, args.metric)
        backend, forecast_values = forecast(values, args.horizon, args.backend)
        result = build_result(
            args.metric,
            values,
            args.horizon,
            backend,
            forecast_values,
        )
    except Exception as exc:
        print(f"forecast failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
