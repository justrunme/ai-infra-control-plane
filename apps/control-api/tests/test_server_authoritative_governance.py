"""Server-authoritative quota/cost, approvals, OCI signature, GitOps manifest."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.decision_store import DecisionStore, reset_decision_store
from app.governance_service import GovernanceEvaluateRequest
from app.policy_source import (
    PolicySource,
    default_verify_signature_for_type,
    materialize_policy_root,
    policy_source_from_env,
)
from app.settings import clear_settings_cache

client = TestClient(app_main.app)


def test_quota_bypass_attempt_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Client requests_last_minute=1 must not bypass a Redis counter at limit."""
    from app import governance_inputs as inputs_module
    from app.prometheus_service import PrometheusSignals
    from app.quota_state_service import QuotaStateSnapshot

    monkeypatch.setenv("QUOTA_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("OIDC_JWT_VERIFY", "true")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://example.invalid/jwks")
    clear_settings_cache()

    monkeypatch.setattr(
        inputs_module,
        "read_quota_state",
        lambda team: QuotaStateSnapshot(
            team=team,
            requests_last_minute=30,
            tokens_today=0,
            source="redis",
        ),
    )
    monkeypatch.setattr(
        inputs_module,
        "fetch_prometheus_signals",
        lambda **_: PrometheusSignals(enabled=False),
    )
    monkeypatch.setattr(
        "app.server_signals.allow_client_governance_signals",
        lambda headers=None: False,
    )

    payload = GovernanceEvaluateRequest(
        team="finance",
        requests_last_minute=1,
        tokens_today=0,
        sensitive_data=False,
        model="llama3.1:8b",
        namespace="ai-dev",
    )
    enriched, snapshot, _ = inputs_module.enrich_governance_request(payload)
    assert snapshot is not None
    assert enriched.requests_last_minute == 30
    assert enriched.sensitive_data is True  # finance classification

    response = client.post(
        "/governance/evaluate",
        json={
            "team": "finance",
            "owner": "bob",
            "environment": "development",
            "namespace": "ai-dev",
            "action": "invoke_model",
            "model": "llama3.1:8b",
            "provider": "ollama",
            "requests_last_minute": 1,
            "sensitive_data": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["final_verdict"] == "block"
    assert body["stages"]["quota"]["decision"] == "block"

    monkeypatch.delenv("QUOTA_REDIS_URL", raising=False)
    monkeypatch.delenv("OIDC_JWT_VERIFY", raising=False)
    clear_settings_cache()


def test_self_approval_forbidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "self-approve.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.delenv("OIDC_JWT_VERIFY", raising=False)
    monkeypatch.delenv("TENANT_ISOLATION", raising=False)
    clear_settings_cache()
    reset_decision_store(None)
    store = DecisionStore.from_env()
    reset_decision_store(store)

    decision_id = store.create_decision(
        final_verdict="approval_required",
        team="platform",
        tenant_id="platform",
        subject="alice",
        request={"subject": "alice", "owner": "alice"},
    )
    approval_id = store.create_approval(decision_id, ttl_seconds=3600)

    response = client.post(
        f"/approvals/{approval_id}/approve",
        json={"reviewer": "alice", "comment": "self"},
    )
    assert response.status_code == 403
    assert "self-approval" in response.json()["detail"]["error"]

    ok = client.post(
        f"/approvals/{approval_id}/approve",
        json={"reviewer": "secops", "comment": "ok"},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "approved"

    reset_decision_store(None)
    store.close()
    clear_settings_cache()


def test_concurrent_approve_one_success_one_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "race.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    clear_settings_cache()
    reset_decision_store(None)
    store = DecisionStore.from_env()

    decision_id = store.create_decision(
        final_verdict="approval_required",
        team="platform",
        tenant_id="platform",
        subject="alice",
        request={"subject": "alice", "owner": "alice"},
    )
    approval_id = store.create_approval(decision_id, ttl_seconds=3600)

    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def _resolve(reviewer: str) -> None:
        barrier.wait()
        try:
            store.resolve_approval(
                approval_id,
                status="approved",
                reviewer=reviewer,
                comment="race",
            )
            outcomes.append("ok")
        except ValueError:
            outcomes.append("conflict")
        except PermissionError:
            outcomes.append("forbidden")

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(
            pool.map(
                _resolve,
                ["bob", "carol"],
            )
        )

    assert outcomes.count("ok") == 1
    assert outcomes.count("conflict") == 1
    record = store.get_approval(approval_id)
    assert record is not None
    assert record.status == "approved"

    store.close()
    reset_decision_store(None)
    clear_settings_cache()


def test_oci_signature_verification_defaults_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POLICY_SOURCE_VERIFY_SIGNATURE", raising=False)
    monkeypatch.setenv("POLICY_SOURCE_TYPE", "oci")
    monkeypatch.setenv("POLICY_SOURCE_OCI_REF", "ghcr.io/example/policies:latest")
    source = policy_source_from_env()
    assert source.verify_signature is True
    assert default_verify_signature_for_type("oci") is True
    assert default_verify_signature_for_type("filesystem") is False


def test_unsigned_oci_bundle_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = PolicySource(
        type="oci",
        reference="ghcr.io/example/policies:unsigned",
        verify_signature=True,
    )

    def _boom(reference: str, *, digest: str = "") -> None:
        raise RuntimeError("no matching signatures")

    monkeypatch.setattr("app.policy_source._cosign_verify_oci", _boom)
    with pytest.raises(RuntimeError, match="signature"):
        materialize_policy_root(source, default_root=tmp_path)

    # Opt-out for local unsigned pulls.
    monkeypatch.setenv("POLICY_SOURCE_VERIFY_SIGNATURE", "false")
    monkeypatch.setenv("POLICY_SOURCE_TYPE", "oci")
    monkeypatch.setenv("POLICY_SOURCE_OCI_REF", "ghcr.io/example/policies:dev")
    opted = policy_source_from_env()
    assert opted.verify_signature is False


def test_gitops_manifest_contains_yaml_patch() -> None:
    from app.gitops_provider import GitOpsPullRequestRequest, render_remediation_manifest

    rendered = render_remediation_manifest(
        GitOpsPullRequestRequest(
            proposal_id="abcd1234-ffff-eeee-dddd-000011112222",
            title="fix: drift",
            body="body",
            tenant_id="platform",
            remediation_kind="pull_model",
            selected_action={
                "kind": "pull_model",
                "model": "llama3.1:8b",
                "backend": "ollama",
            },
        )
    )
    assert "aiControlPlane" in rendered
    assert "replicas" in rendered
    assert "llama3.1:8b" in rendered
    assert rendered.strip().startswith("#")


def test_github_provider_idempotent_and_commits_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import base64
    import json

    import httpx

    from app.gitops_provider import GitHubPullRequestProvider, GitOpsPullRequestRequest

    proposal_id = "abcd1234-ffff-eeee-dddd-000011112222"
    created_prs = 0
    put_bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal created_prs
        path = request.url.path
        if path.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "abc123"}})
        if f"/git/ref/heads/remediation/{proposal_id}" in path:
            return httpx.Response(404, json={"message": "Not Found"})
        if path.endswith("/git/refs") and request.method == "POST":
            return httpx.Response(
                201, json={"ref": f"refs/heads/remediation/{proposal_id}"}
            )
        if "/contents/remediation/proposals/" in path and request.method == "GET":
            return httpx.Response(404, json={"message": "Not Found"})
        if "/contents/remediation/proposals/" in path and request.method == "PUT":
            body = json.loads(request.content.decode("utf-8"))
            put_bodies.append(body)
            return httpx.Response(201, json={"content": {"path": path}})
        if path.endswith("/pulls") and request.method == "GET":
            if created_prs == 0:
                return httpx.Response(200, json=[])
            return httpx.Response(
                200,
                json=[
                    {
                        "html_url": "https://github.com/acme/platform/pull/42",
                        "draft": True,
                        "head": {"sha": "deadbeef"},
                    }
                ],
            )
        if path.endswith("/pulls") and request.method == "POST":
            created_prs += 1
            return httpx.Response(
                201,
                json={
                    "html_url": "https://github.com/acme/platform/pull/42",
                    "draft": True,
                    "head": {"sha": "deadbeef"},
                },
            )
        return httpx.Response(500, json={"message": f"unexpected {path}"})

    transport = httpx.MockTransport(handler)
    client_http = httpx.Client(
        transport=transport, base_url="https://api.github.com"
    )
    provider = GitHubPullRequestProvider(
        token="ghs_test",
        repository="acme/platform",
        client=client_http,
    )
    req = GitOpsPullRequestRequest(
        proposal_id=proposal_id,
        title="fix: drift",
        body="body",
        tenant_id="platform",
        remediation_kind="pull_model",
        selected_action={"model": "llama3.1:8b", "backend": "ollama"},
    )
    first = provider.create_draft_pull_request(req)
    assert first.created is True
    assert first.pr_url.endswith("/pull/42")

    # Second call should reuse the open PR.
    second = provider.create_draft_pull_request(req)
    assert second.created is False
    assert second.pr_url == first.pr_url
    assert created_prs == 1

    decoded = [
        base64.b64decode(item["content"]).decode("utf-8") for item in put_bodies
    ]
    assert any("values.patch.yaml" in (b.get("message") or "") or "aiControlPlane" in text
               for b, text in zip(put_bodies, decoded, strict=False) for _ in [0])
    assert any("aiControlPlane" in text for text in decoded)
    assert any("replicas" in text for text in decoded)
    client_http.close()


def test_atomic_incr_quota_counters(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import quota_state_service as quota_mod

    mock_client = MagicMock()
    mock_client.eval.return_value = [5, 1200]
    monkeypatch.setenv("QUOTA_REDIS_URL", "redis://localhost:6379/0")

    import redis

    monkeypatch.setattr(
        redis.Redis, "from_url", lambda *_args, **_kwargs: mock_client
    )
    snap = quota_mod.incr_quota_counters("finance", tokens=100)
    assert snap is not None
    assert snap.requests_last_minute == 5
    assert snap.tokens_today == 1200
    mock_client.eval.assert_called_once()
    mock_client.close.assert_called_once()
