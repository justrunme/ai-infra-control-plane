"""Tests for named policy packs in the governance pipeline."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def pack_config(pack_module: ModuleType) -> dict:
    return pack_module.parse_packs(REPO_ROOT / "governance/policy-packs/packs.yaml")


@pytest.fixture(scope="session")
def registry_models(registry_module: ModuleType) -> set[str]:
    registry = registry_module.parse_registry(
        REPO_ROOT / "governance/registry/models.yaml"
    )
    return set(registry.keys())


def base_request(**overrides) -> dict:
    payload = {
        "team": "platform",
        "owner": "alice",
        "environment": "development",
        "namespace": "ai-dev",
        "action": "invoke_model",
        "model": "llama3.1:8b",
        "provider": "ollama",
        "input_tokens": 100,
        "output_tokens": 50,
        "sensitive_data": False,
        "requests_last_minute": 0,
        "tokens_today": 0,
        "policy_pack": "",
    }
    payload.update(overrides)
    return payload


def test_resolve_pack_from_environment(
    pack_module: ModuleType, pack_config: dict
) -> None:
    request = base_request(environment="production", policy_pack="")
    result = pack_module.evaluate_pack(
        request, pack_config, registry_models={"llama3.1:8b"}
    )
    assert result["pack"] == "production"


def test_production_pack_blocks_unregistered_model(
    pack_module: ModuleType,
    pack_config: dict,
    registry_models: set[str],
) -> None:
    request = base_request(
        environment="production",
        policy_pack="production",
        model="experimental-model",
    )
    result = pack_module.evaluate_pack(
        request, pack_config, registry_models=registry_models
    )
    assert result["decision"] == "block"
    assert "unregistered model" in result["reasons"][0]


def test_production_pack_requires_production_environment(
    pack_module: ModuleType, pack_config: dict
) -> None:
    request = base_request(policy_pack="production", environment="development")
    result = pack_module.evaluate_pack(
        request, pack_config, registry_models={"llama3.1:8b"}
    )
    assert result["decision"] == "block"
    assert "requires environment production" in result["reasons"][0]


def test_research_pack_relaxes_quota(
    pack_module: ModuleType,
    pack_config: dict,
    registry_models: set[str],
    quota_module: ModuleType,
) -> None:
    request = base_request(
        team="finance",
        requests_last_minute=50,
        policy_pack="research",
    )
    pack = pack_module.evaluate_pack(
        request, pack_config, registry_models=registry_models
    )
    request["_pack_quota_multiplier"] = pack["quota_multiplier"]

    quota_policies = quota_module.parse_policies(
        REPO_ROOT / "governance/quota/policies.yaml"
    )
    quota = quota_module.evaluate_request(request, quota_policies)

    assert pack["pack"] == "research"
    assert quota["decision"] == "allow"
