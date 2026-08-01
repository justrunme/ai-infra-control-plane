"""Policy source failure modes and readiness fail-closed behavior."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.policy_lifecycle import get_policy_lifecycle, reset_policy_lifecycle
from app.policy_source import get_policy_failure_mode
from app.settings import clear_settings_cache

client = TestClient(app_main.app)


def test_failure_mode_defaults_to_last_known_good(monkeypatch) -> None:
    monkeypatch.delenv("POLICY_SOURCE_FAILURE_MODE", raising=False)
    assert get_policy_failure_mode() == "last_known_good"


def test_fail_closed_bootstrap_marks_not_ready(monkeypatch) -> None:
    monkeypatch.setenv("POLICY_SOURCE_FAILURE_MODE", "fail_closed")
    monkeypatch.setenv("POLICY_SOURCE_TYPE", "oci")
    monkeypatch.setenv("POLICY_SOURCE_OCI_REF", "ghcr.io/example/missing:latest")
    monkeypatch.setenv("POLICY_SOURCE_VERIFY_SIGNATURE", "false")
    clear_settings_cache()
    reset_policy_lifecycle()

    life = get_policy_lifecycle()
    with pytest.raises(RuntimeError):
        life.ensure_bootstrapped()
    status = life.bootstrap_status()
    assert status["error"]
    assert status["ok"] is False

    monkeypatch.setattr(
        "app.policy_lifecycle.get_policy_lifecycle",
        lambda: life,
    )
    monkeypatch.setattr(
        "app.routers.health.get_policy_lifecycle",
        lambda: life,
    )
    response = client.get("/readyz")
    # Embedded bundle may still validate; fail_closed with bootstrap error → 503.
    assert response.status_code == 503
    body = response.json()
    detail = body.get("detail") or body.get("error") or body
    if isinstance(detail, dict) and "policy_bundle_ok" in detail:
        assert detail["policy_bundle_ok"] is False
    else:
        # Unified error envelope wraps detail.
        nested = body.get("detail", {})
        assert nested.get("policy_bundle_ok") is False or "not ready" in str(body)

    monkeypatch.delenv("POLICY_SOURCE_FAILURE_MODE", raising=False)
    monkeypatch.delenv("POLICY_SOURCE_TYPE", raising=False)
    monkeypatch.delenv("POLICY_SOURCE_OCI_REF", raising=False)
    reset_policy_lifecycle()
    clear_settings_cache()
