"""Tests for governance PolicyBundle loading and caching."""

from __future__ import annotations

from pathlib import Path

from app.governance_service import get_governance_root
from app.policy_bundle import (
    PolicyBundle,
    clear_policy_bundle,
    get_policy_bundle,
    reload_policy_bundle,
)


def test_policy_bundle_load_ok() -> None:
    root = get_governance_root()
    bundle = PolicyBundle.load(root)

    assert bundle.validation_status == "ok"
    assert bundle.error is None
    assert len(bundle.content_digest) == 64
    assert bundle.bundle_id == bundle.content_digest[:12]
    assert bundle.git_revision
    assert bundle.packs is not None
    assert bundle.quota_policies is not None
    assert bundle.registry is not None
    assert bundle.residency is not None
    assert bundle.agents is not None
    assert bundle.tools is not None
    assert bundle.cost_policies is not None
    assert bundle.risk_rules is not None
    assert set(bundle.modules) == {
        "packs",
        "quota",
        "registry",
        "sovereign",
        "agents",
        "tools",
        "cost",
        "risk",
        "approval",
        "prompt",
    }


def test_policy_bundle_load_missing_root(tmp_path: Path) -> None:
    bundle = PolicyBundle.load(tmp_path / "missing")
    assert bundle.validation_status == "error"
    assert bundle.error


def test_get_policy_bundle_lazy_and_reload(monkeypatch) -> None:
    clear_policy_bundle()
    monkeypatch.setenv("GIT_COMMIT", "abc123deadbeef")

    first = get_policy_bundle()
    second = get_policy_bundle()
    assert first is second
    assert first.git_revision == "abc123deadbeef"
    assert first.validation_status == "ok"

    reloaded = reload_policy_bundle()
    assert reloaded is not first
    assert reloaded.git_revision == "abc123deadbeef"
    assert get_policy_bundle() is reloaded

    clear_policy_bundle()
