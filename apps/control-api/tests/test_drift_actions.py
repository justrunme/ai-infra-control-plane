"""Drift suggested remediation actions."""

from __future__ import annotations

from app.drift_actions import build_drift_actions
from app.drift_service import BackendDrift, DriftStatus


def test_drift_actions_for_missing_model() -> None:
    status = DriftStatus(
        updated_at="2026-01-01T00:00:00+00:00",
        in_sync=False,
        summary="configured inventory differs from live backend probes",
        backends=[
            BackendDrift(
                backend="ollama",
                probe_healthy=True,
                desired_models=["llama3.1:8b"],
                actual_models=[],
                missing_on_backend=["llama3.1:8b"],
                unexpected_on_backend=[],
                in_sync=False,
            ),
            BackendDrift(
                backend="vllm",
                probe_healthy=True,
                desired_models=[],
                actual_models=[],
                missing_on_backend=[],
                unexpected_on_backend=[],
                in_sync=True,
            ),
        ],
    )
    result = build_drift_actions(status)
    assert result.in_sync is False
    kinds = {item.kind for item in result.actions}
    assert "pull_model" in kinds
    assert "open_github_issue" in kinds
    assert "open_github_pr" in kinds
    pull = next(item for item in result.actions if item.kind == "pull_model")
    assert pull.command == "ollama pull llama3.1:8b"


def test_drift_actions_empty_when_in_sync() -> None:
    status = DriftStatus(
        updated_at="2026-01-01T00:00:00+00:00",
        in_sync=True,
        summary="ok",
        backends=[],
    )
    assert build_drift_actions(status).actions == []
