"""Tests for model registry attestation signing."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SIGNING_PATH = REPO_ROOT / "governance/registry/signing.py"
REGISTRY_PATH = REPO_ROOT / "governance/registry/models.yaml"


def _load_signing():
    spec = importlib.util.spec_from_file_location("registry_signing_test", SIGNING_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sign_and_verify_registry_entry() -> None:
    signing = _load_signing()
    entry = {
        "revision": "v1",
        "artifact_digest": "sha256:demo",
        "risk_tier": "low",
        "license": "apache-2.0",
    }
    signature = signing.sign_entry("demo-model", entry, secret="test-secret")
    entry["attestation_signature"] = signature
    assert signing.verify_entry_signature("demo-model", entry, secret="test-secret")


def test_allowed_teams_blocks_unlisted_team(registry_module) -> None:
    registry = registry_module.parse_registry(REGISTRY_PATH)
    result = registry_module.evaluate_model_policy(
        {
            "model": "qwen2.5-7b",
            "team": "finance",
            "namespace": "ai-dev",
            "sensitive_data": False,
            "forecast_monthly_cost_usd": 100,
        },
        registry,
    )
    assert result["forbidden"] is True
    assert any("team finance" in reason for reason in result["reasons"])
