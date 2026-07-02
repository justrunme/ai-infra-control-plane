"""Shared helpers to load the standalone governance/forecasting scripts.

These modules are CLI scripts rather than an installable package, so tests load
them by file path with importlib instead of a regular import.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str) -> ModuleType:
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def cost_module() -> ModuleType:
    return load_module("cost_governance", "governance/cost/evaluate.py")


@pytest.fixture(scope="session")
def risk_module() -> ModuleType:
    return load_module("risk_governance", "governance/risk/evaluate.py")


@pytest.fixture(scope="session")
def approval_module() -> ModuleType:
    return load_module("approval_governance", "governance/approval/evaluate.py")


@pytest.fixture(scope="session")
def pipeline_module() -> ModuleType:
    return load_module("governance_pipeline", "governance/pipeline/run_pipeline.py")


@pytest.fixture(scope="session")
def forecast_module() -> ModuleType:
    return load_module("timesfm_forecast", "forecasting/timesfm/forecast.py")


@pytest.fixture(scope="session")
def registry_module() -> ModuleType:
    return load_module("model_registry", "governance/registry/evaluate.py")


@pytest.fixture(scope="session")
def quota_module() -> ModuleType:
    return load_module("quota_governance", "governance/quota/evaluate.py")


@pytest.fixture(scope="session")
def pack_module() -> ModuleType:
    return load_module("policy_packs", "governance/policy-packs/evaluate.py")


@pytest.fixture(scope="session")
def fleet_module() -> ModuleType:
    return load_module("fleet_evaluate", "fleet/evaluate.py")


@pytest.fixture(scope="session")
def risk_rules(risk_module: ModuleType) -> dict:
    return risk_module.parse_rules(REPO_ROOT / "governance/risk/rules.yaml")


@pytest.fixture(scope="session")
def cost_policies(cost_module: ModuleType) -> dict:
    return cost_module.parse_policy_file(REPO_ROOT / "governance/cost/policies.yaml")
