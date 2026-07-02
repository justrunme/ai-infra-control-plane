#!/usr/bin/env python3
"""Parse fleet cluster registry and evaluate multi-cluster health."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal


def parse_scalar(value: str) -> Any:
    normalized = value.strip()
    if normalized == "":
        return ""
    if normalized.lower() in {"true", "yes"}:
        return True
    if normalized.lower() in {"false", "no"}:
        return False
    try:
        if "." in normalized:
            return float(normalized)
        return int(normalized)
    except ValueError:
        return normalized


def parse_clusters(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"fleet cluster file does not exist: {path}")

    clusters: dict[str, dict[str, Any]] = {}
    section: str | None = None
    current_cluster: str | None = None

    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0 and line == "clusters:":
            section = "clusters"
            continue

        if section != "clusters":
            raise ValueError(f"unsupported fleet registry line: {raw_line}")

        if indent == 2 and line.endswith(":"):
            current_cluster = line[:-1]
            clusters[current_cluster] = {}
            continue

        if indent == 4 and current_cluster is not None:
            key, _, value = line.partition(":")
            if not key or not value:
                raise ValueError(f"unsupported fleet cluster entry: {raw_line}")
            clusters[current_cluster][key] = parse_scalar(value)
            continue

        raise ValueError(f"unsupported fleet registry line: {raw_line}")

    return clusters


ProbeFn = Callable[[str], tuple[bool, int, str | None]]


def cluster_health(
    *,
    ollama_healthy: bool | None,
    vllm_healthy: bool | None,
) -> Literal["healthy", "degraded", "unknown", "unreachable"]:
    if ollama_healthy is None and vllm_healthy is None:
        return "unknown"
    if ollama_healthy is False and vllm_healthy is False:
        return "unreachable"
    if ollama_healthy is False or vllm_healthy is False:
        return "degraded"
    return "healthy"


def evaluate_cluster(
    cluster_id: str,
    spec: dict[str, Any],
    *,
    probe_ollama: ProbeFn,
    probe_vllm: ProbeFn,
    primary_ollama_url: str,
    primary_vllm_url: str,
) -> dict[str, Any]:
    probe_enabled = bool(spec.get("probe_enabled", False))
    ollama_url = str(spec.get("ollama_base_url") or primary_ollama_url)
    vllm_url = str(spec.get("vllm_base_url") or primary_vllm_url)

    if probe_enabled:
        ollama_healthy, ollama_latency_ms, ollama_error = probe_ollama(ollama_url)
        vllm_healthy, vllm_latency_ms, vllm_error = probe_vllm(vllm_url)
    else:
        ollama_healthy = spec.get("ollama_healthy")
        vllm_healthy = spec.get("vllm_healthy")
        ollama_latency_ms = int(spec.get("ollama_latency_ms", 0))
        vllm_latency_ms = int(spec.get("vllm_latency_ms", 0))
        ollama_error = None if ollama_healthy else "static registry marks ollama degraded"
        vllm_error = None if vllm_healthy else "static registry marks vllm degraded"

    return {
        "id": cluster_id,
        "label": str(spec.get("label", cluster_id)),
        "cloud": str(spec.get("cloud", "unknown")),
        "region": str(spec.get("region", "unknown")),
        "environment": str(spec.get("environment", "development")),
        "primary": bool(spec.get("primary", False)),
        "probe_enabled": probe_enabled,
        "health": cluster_health(
            ollama_healthy=ollama_healthy,
            vllm_healthy=vllm_healthy,
        ),
        "node_count": int(spec.get("node_count", 0)),
        "healthy_models": int(spec.get("healthy_models", 0)),
        "ollama": {
            "healthy": ollama_healthy,
            "latency_ms": ollama_latency_ms,
            "error": ollama_error,
        },
        "vllm": {
            "healthy": vllm_healthy,
            "latency_ms": vllm_latency_ms,
            "error": vllm_error,
        },
    }


def evaluate_fleet(
    clusters: dict[str, dict[str, Any]],
    *,
    probe_ollama: ProbeFn,
    probe_vllm: ProbeFn,
    primary_ollama_url: str,
    primary_vllm_url: str,
) -> list[dict[str, Any]]:
    return [
        evaluate_cluster(
            cluster_id,
            spec,
            probe_ollama=probe_ollama,
            probe_vllm=probe_vllm,
            primary_ollama_url=primary_ollama_url,
            primary_vllm_url=primary_vllm_url,
        )
        for cluster_id, spec in clusters.items()
    ]
