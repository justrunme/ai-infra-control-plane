"""GitOpsProvider: noop default + mocked GitHub draft PR adapter."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.decision_store import DecisionStore, reset_decision_store
from app.drift_service import BackendDrift, DriftStatus
from app.gitops_provider import (
    GitHubPullRequestProvider,
    GitOpsProviderError,
    GitOpsPullRequestRequest,
    NullGitOpsProvider,
    build_gitops_provider,
    reset_gitops_provider,
    resolve_gitops_provider_name,
)
from app.remediation_service import RemediationError, prepare_pr_draft
from app.settings import clear_settings_cache


def _approved_proposal(store: DecisionStore) -> str:
    drift = DriftStatus(
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
            )
        ],
    )
    return store.create_remediation_proposal(
        tenant_id="platform",
        status="approved",
        source="test",
        remediation_kind="pull_model",
        drift_snapshot=drift.model_dump(),
        selected_action={"title": "Pull model", "kind": "pull_model"},
    )


@pytest.fixture(autouse=True)
def _reset_provider() -> None:
    reset_gitops_provider(None)
    yield
    reset_gitops_provider(None)


def test_resolve_defaults_to_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITOPS_PROVIDER", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert resolve_gitops_provider_name() == "noop"
    assert isinstance(build_gitops_provider(), NullGitOpsProvider)


def test_resolve_github_when_token_and_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/platform")
    assert resolve_gitops_provider_name() == "github"
    monkeypatch.setenv("GITOPS_PROVIDER", "noop")
    assert resolve_gitops_provider_name() == "noop"


def test_github_provider_creates_draft_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        path = request.url.path
        if path.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "abc123"}})
        if path.endswith("/git/ref/heads/remediation/abcd1234"):
            return httpx.Response(404, json={"message": "Not Found"})
        if path.endswith("/git/refs") and request.method == "POST":
            return httpx.Response(201, json={"ref": "refs/heads/remediation/abcd1234"})
        if "/contents/remediation/proposals/" in path and request.method == "GET":
            return httpx.Response(404, json={"message": "Not Found"})
        if "/contents/remediation/proposals/" in path and request.method == "PUT":
            return httpx.Response(201, json={"content": {"path": path}})
        if path.endswith("/pulls") and request.method == "POST":
            body = request.read()
            assert b'"draft": true' in body or b'"draft":true' in body
            return httpx.Response(
                201,
                json={
                    "html_url": "https://github.com/acme/platform/pull/42",
                    "draft": True,
                },
            )
        return httpx.Response(500, json={"message": f"unexpected {path}"})

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.github.com",
    )
    provider = GitHubPullRequestProvider(
        token="ghs_test",
        repository="acme/platform",
        client=client,
    )
    result = provider.create_draft_pull_request(
        GitOpsPullRequestRequest(
            proposal_id="abcd1234-ffff-eeee-dddd-000011112222",
            title="fix: drift",
            body="body",
            tenant_id="platform",
            remediation_kind="pull_model",
        )
    )
    assert result.created is True
    assert result.provider == "github"
    assert result.pr_url == "https://github.com/acme/platform/pull/42"
    assert any(c.startswith("POST ") and c.endswith("/pulls") for c in calls)
    client.close()


def test_build_gitops_provider_github(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITOPS_PROVIDER", "github")
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_test")
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/platform")
    provider = build_gitops_provider()
    assert isinstance(provider, GitHubPullRequestProvider)


def test_github_provider_updates_existing_note() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "abc123"}})
        if "/git/ref/heads/remediation/" in path and request.method == "GET":
            return httpx.Response(200, json={"object": {"sha": "abc123"}})
        if "/contents/remediation/proposals/" in path and request.method == "GET":
            return httpx.Response(200, json={"sha": "file-sha"})
        if "/contents/remediation/proposals/" in path and request.method == "PUT":
            return httpx.Response(200, json={"content": {"sha": "new"}})
        if path.endswith("/pulls"):
            return httpx.Response(
                201,
                json={"html_url": "https://github.com/acme/platform/pull/7", "draft": True},
            )
        return httpx.Response(500, text=path)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.github.com",
    )
    provider = GitHubPullRequestProvider(
        token="ghs_test",
        repository="acme/platform",
        client=client,
    )
    result = provider.create_draft_pull_request(
        GitOpsPullRequestRequest(proposal_id="zzzzzzzz-1", title="t", body="b")
    )
    assert result.pr_url.endswith("/pull/7")
    client.close()


def test_github_provider_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bad credentials"})

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.github.com",
    )
    provider = GitHubPullRequestProvider(
        token="bad",
        repository="acme/platform",
        client=client,
    )
    with pytest.raises(GitOpsProviderError):
        provider.create_draft_pull_request(
            GitOpsPullRequestRequest(
                proposal_id="p1",
                title="t",
                body="b",
            )
        )
    client.close()


def test_prepare_pr_draft_uses_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "gitops.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    clear_settings_cache()
    reset_decision_store(None)
    store = DecisionStore.from_env()
    reset_decision_store(store)

    proposal_id = _approved_proposal(store)

    class FakeProvider:
        def create_draft_pull_request(self, request):
            assert request.proposal_id == proposal_id
            from app.gitops_provider import GitOpsPullRequestResult

            return GitOpsPullRequestResult(
                pr_url="https://example.test/pr/1",
                provider="github",
                draft=True,
                created=True,
            )

    reset_gitops_provider(FakeProvider())
    updated = prepare_pr_draft(proposal_id, store=store)
    assert updated.status == "pr_created"
    assert updated.pr_url == "https://example.test/pr/1"
    assert updated.pr_title

    reset_decision_store(None)
    store.close()
    clear_settings_cache()


def test_prepare_pr_draft_provider_failure_keeps_approved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "gitops-fail.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    clear_settings_cache()
    reset_decision_store(None)
    store = DecisionStore.from_env()
    reset_decision_store(store)
    proposal_id = _approved_proposal(store)

    class Boom:
        def create_draft_pull_request(self, request):
            raise GitOpsProviderError("boom")

    reset_gitops_provider(Boom())
    with pytest.raises(RemediationError, match="boom"):
        prepare_pr_draft(proposal_id, store=store)
    still = store.get_remediation_proposal(proposal_id)
    assert still is not None
    assert still.status == "approved"

    reset_decision_store(None)
    store.close()
    clear_settings_cache()


def test_prepare_pr_skips_network_when_url_provided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "gitops-url.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    clear_settings_cache()
    reset_decision_store(None)
    store = DecisionStore.from_env()
    reset_decision_store(store)
    proposal_id = _approved_proposal(store)

    class MustNotCall:
        def create_draft_pull_request(self, request):
            raise AssertionError("provider should not be called")

    reset_gitops_provider(MustNotCall())
    updated = prepare_pr_draft(
        proposal_id,
        pr_url="https://github.com/acme/platform/pull/9",
        store=store,
    )
    assert updated.pr_url.endswith("/pull/9")

    reset_decision_store(None)
    store.close()
    clear_settings_cache()
