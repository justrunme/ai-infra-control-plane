"""Unit tests for inventory drift detection."""

from __future__ import annotations

from app.drift_service import (
    build_backend_drift,
    build_drift_status,
    diff_models,
    match_names,
    normalize_model_name,
)


class InventoryEntry:
    def __init__(self, name: str, backend: str) -> None:
        self.name = name
        self.backend = backend


def test_normalize_model_name() -> None:
    assert normalize_model_name("llama-3.1-8b-instruct") == "llama318binstruct"
    assert normalize_model_name("llama3.1:8b") == "llama318b"


def test_match_names_fuzzy() -> None:
    assert match_names("llama-3.1-8b-instruct", "llama3.1:8b")
    assert match_names("qwen2.5-14b-instruct", "qwen2.5-14b")


def test_diff_models_detects_missing_and_unexpected() -> None:
    missing, unexpected = diff_models(
        ["llama-3.1-8b-instruct", "qwen2.5-14b-instruct"],
        ["llama3.1:8b", "mistral:7b"],
    )
    assert missing == ["qwen2.5-14b-instruct"]
    assert unexpected == ["mistral:7b"]


def test_backend_drift_in_sync() -> None:
    inventory = [
        InventoryEntry("llama3.1:8b", "ollama"),
        InventoryEntry("qwen2.5-14b", "vllm"),
    ]
    ollama = build_backend_drift(
        "ollama",
        inventory,
        probe_healthy=True,
        actual_models=["llama3.1:8b"],
        probe_error=None,
    )
    assert ollama.in_sync is True
    assert ollama.missing_on_backend == []
    assert ollama.unexpected_on_backend == []


def test_backend_drift_when_probe_down() -> None:
    inventory = [InventoryEntry("llama3.1:8b", "ollama")]
    drift = build_backend_drift(
        "ollama",
        inventory,
        probe_healthy=False,
        actual_models=[],
        probe_error="connection refused",
    )
    assert drift.in_sync is False
    assert drift.missing_on_backend == ["llama3.1:8b"]
    assert drift.probe_error == "connection refused"


def test_build_drift_status_summary() -> None:
    inventory = [InventoryEntry("llama3.1:8b", "ollama")]
    status = build_drift_status(
        inventory,
        lambda: (["llama3.1:8b"], True, None),
        lambda: ([], False, "down"),
    )
    assert status.in_sync is False
    assert len(status.backends) == 2
    assert status.backends[0].in_sync is True
    assert status.backends[1].in_sync is False
