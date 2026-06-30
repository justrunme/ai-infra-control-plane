"""Compare configured model inventory against live backend probes."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, Protocol

from pydantic import BaseModel, Field


class InventoryModel(Protocol):
    name: str
    backend: str


class BackendDrift(BaseModel):
    backend: Literal["ollama", "vllm"]
    probe_healthy: bool
    probe_error: str | None = None
    desired_models: list[str]
    actual_models: list[str]
    missing_on_backend: list[str]
    unexpected_on_backend: list[str]
    in_sync: bool


class DriftStatus(BaseModel):
    updated_at: str
    in_sync: bool
    summary: str
    backends: list[BackendDrift] = Field(default_factory=list)


def normalize_model_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def match_names(desired: str, actual: str) -> bool:
    left = normalize_model_name(desired)
    right = normalize_model_name(actual)
    return left == right or left in right or right in left


def diff_models(desired: list[str], actual: list[str]) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    for name in desired:
        if not any(match_names(name, live) for live in actual):
            missing.append(name)

    unexpected: list[str] = []
    for name in actual:
        if not any(match_names(name, configured) for configured in desired):
            unexpected.append(name)

    return missing, unexpected


def build_backend_drift(
    backend: Literal["ollama", "vllm"],
    inventory: list[InventoryModel],
    probe_healthy: bool,
    actual_models: list[str],
    probe_error: str | None,
) -> BackendDrift:
    desired = sorted(
        {model.name for model in inventory if model.backend == backend}
    )
    actual = sorted(set(actual_models))
    missing, unexpected = diff_models(desired, actual) if probe_healthy else (desired, [])
    in_sync = probe_healthy and not missing and not unexpected

    return BackendDrift(
        backend=backend,
        probe_healthy=probe_healthy,
        probe_error=probe_error,
        desired_models=desired,
        actual_models=actual,
        missing_on_backend=missing,
        unexpected_on_backend=unexpected,
        in_sync=in_sync,
    )


def build_drift_status(
    inventory: list[InventoryModel],
    ollama_probe: Callable[[], tuple[list[str], bool, str | None]],
    vllm_probe: Callable[[], tuple[list[str], bool, str | None]],
) -> DriftStatus:
    ollama_models, ollama_ok, ollama_error = ollama_probe()
    vllm_models, vllm_ok, vllm_error = vllm_probe()

    backends = [
        build_backend_drift("ollama", inventory, ollama_ok, ollama_models, ollama_error),
        build_backend_drift("vllm", inventory, vllm_ok, vllm_models, vllm_error),
    ]
    in_sync = all(item.in_sync for item in backends)

    if in_sync:
        summary = "configured inventory matches live backend probes"
    elif any(not item.probe_healthy for item in backends):
        summary = "inventory drift or unreachable backend probes detected"
    else:
        summary = "configured inventory differs from live backend probes"

    return DriftStatus(
        updated_at=datetime.now(UTC).isoformat(),
        in_sync=in_sync,
        summary=summary,
        backends=backends,
    )
