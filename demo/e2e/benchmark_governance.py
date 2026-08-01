#!/usr/bin/env python3
"""Concurrent governance evaluate benchmark with p95 SLO gate."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


def _post_evaluate(url: str, payload: bytes, timeout: float) -> float:
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response.read()
        if response.status >= 400:
            raise RuntimeError(f"status={response.status}")
    return (time.perf_counter() - started) * 1000


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8091/governance/evaluate",
        help="Evaluate endpoint URL",
    )
    parser.add_argument("--requests", type=int, default=300)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--p95-max-ms", type=float, default=250.0)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    body = json.dumps(
        {
            "team": "platform",
            "environment": "development",
            "model": "llama3.1:8b",
            "estimated_cost_usd": 0.01,
        }
    ).encode("utf-8")

    latencies: list[float] = []
    errors = 0
    started = time.perf_counter()

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [
            pool.submit(_post_evaluate, args.url, body, args.timeout)
            for _ in range(args.requests)
        ]
        for future in as_completed(futures):
            try:
                latencies.append(future.result())
            except (urllib.error.URLError, TimeoutError, RuntimeError, OSError):
                errors += 1

    elapsed = time.perf_counter() - started
    p95 = percentile(latencies, 95) if latencies else float("inf")
    throughput = (len(latencies) / elapsed) if elapsed > 0 else 0.0
    mean = statistics.fmean(latencies) if latencies else float("nan")

    print(f"requests={args.requests}")
    print(f"concurrency={args.concurrency}")
    print(f"success={len(latencies)}")
    print(f"errors={errors}")
    print(f"mean_ms={mean:.2f}")
    print(f"p95_ms={p95:.2f}")
    print(f"throughput_rps={throughput:.2f}")

    if errors > 0:
        print("FAIL: errors > 0", file=sys.stderr)
        return 1
    if p95 > args.p95_max_ms:
        print(f"FAIL: p95 {p95:.2f} > {args.p95_max_ms}", file=sys.stderr)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
