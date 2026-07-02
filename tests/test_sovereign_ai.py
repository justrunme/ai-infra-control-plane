"""Unit tests for sovereign AI residency."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESIDENCY_PATH = REPO_ROOT / "governance/sovereign/residency.yaml"
MODELS_PATH = REPO_ROOT / "governance/registry/models.yaml"


def test_parse_residency(sovereign_module) -> None:
    residency = sovereign_module.parse_residency(RESIDENCY_PATH)
    assert residency["regions"]["eu-central"]["block_external_providers"] is True


def test_blocks_external_model_in_eu(registry_module, sovereign_module) -> None:
    registry = registry_module.parse_registry(MODELS_PATH)
    residency = sovereign_module.parse_residency(RESIDENCY_PATH)
    entry = registry_module.lookup_model(registry, "gpt-4.1-mini")
    result = sovereign_module.evaluate_residency(
        {
            "model": "gpt-4.1-mini",
            "provider": "openai",
            "region": "eu-central",
        },
        residency,
        entry,
    )
    assert result["forbidden"] is True


def test_allows_local_model_in_eu(registry_module, sovereign_module) -> None:
    registry = registry_module.parse_registry(MODELS_PATH)
    residency = sovereign_module.parse_residency(RESIDENCY_PATH)
    entry = registry_module.lookup_model(registry, "llama3.1:8b")
    result = sovereign_module.evaluate_residency(
        {
            "model": "llama3.1:8b",
            "provider": "ollama",
            "region": "eu-central",
        },
        residency,
        entry,
    )
    assert result["forbidden"] is False
