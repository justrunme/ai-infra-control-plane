"""Optional GitOps adapters for opening draft pull requests.

Default is a no-op provider (title/body only). When ``GITHUB_TOKEN`` and
``GITHUB_REPOSITORY`` are set (or ``GITOPS_PROVIDER=github``), the control plane
can open a **draft** GitHub PR. It never mutates cluster inventory or backends.
"""

from __future__ import annotations

import base64
import os
import threading
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.settings import get_settings

_provider: GitOpsProvider | None = None
_provider_lock = threading.Lock()


@dataclass(frozen=True)
class GitOpsPullRequestRequest:
    proposal_id: str
    title: str
    body: str
    tenant_id: str = ""
    remediation_kind: str = ""


@dataclass(frozen=True)
class GitOpsPullRequestResult:
    pr_url: str | None
    provider: str
    draft: bool
    created: bool
    detail: str = ""


class GitOpsProvider(Protocol):
    def create_draft_pull_request(
        self, request: GitOpsPullRequestRequest
    ) -> GitOpsPullRequestResult: ...


class NullGitOpsProvider:
    """Default: persist draft text only; no remote PR."""

    def create_draft_pull_request(
        self, request: GitOpsPullRequestRequest
    ) -> GitOpsPullRequestResult:
        return GitOpsPullRequestResult(
            pr_url=None,
            provider="noop",
            draft=True,
            created=False,
            detail="draft-only",
        )


class GitOpsProviderError(RuntimeError):
    """Raised when a configured GitOps provider fails to open a PR."""


class GitHubPullRequestProvider:
    """Open a draft GitHub PR with a remediation note commit (GitOps-safe)."""

    def __init__(
        self,
        *,
        token: str,
        repository: str,
        api_url: str = "https://api.github.com",
        base_branch: str = "main",
        draft: bool = True,
        client: httpx.Client | None = None,
    ) -> None:
        if "/" not in repository:
            raise ValueError("GITHUB_REPOSITORY must be owner/repo")
        self._token = token
        self._owner, self._repo = repository.split("/", 1)
        self._api_url = api_url.rstrip("/")
        self._base_branch = base_branch
        self._draft = draft
        self._client = client

    def create_draft_pull_request(
        self, request: GitOpsPullRequestRequest
    ) -> GitOpsPullRequestResult:
        branch = f"remediation/{request.proposal_id[:8]}"
        path = f"remediation/proposals/{request.proposal_id}.md"
        note = (
            f"# Remediation proposal `{request.proposal_id}`\n\n"
            f"- Tenant: `{request.tenant_id or 'n/a'}`\n"
            f"- Kind: `{request.remediation_kind or 'n/a'}`\n\n"
            f"{request.body}\n"
        )
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        owns_client = self._client is None
        client = self._client or httpx.Client(
            base_url=self._api_url,
            headers=headers,
            timeout=30.0,
            trust_env=get_settings().http_trust_env,
        )
        try:
            if owns_client:
                client.headers.update(headers)
            sha = self._default_branch_sha(client)
            self._ensure_branch(client, branch=branch, sha=sha)
            self._put_file(
                client,
                path=path,
                content=note,
                branch=branch,
                message=f"chore: remediation note for {request.proposal_id[:8]}",
            )
            pr = self._create_pull_request(
                client,
                title=request.title,
                body=request.body,
                head=branch,
            )
            html_url = str(pr.get("html_url") or "")
            if not html_url:
                raise GitOpsProviderError("GitHub pull request missing html_url")
            return GitOpsPullRequestResult(
                pr_url=html_url,
                provider="github",
                draft=bool(pr.get("draft", self._draft)),
                created=True,
                detail="draft pull request created",
            )
        except GitOpsProviderError:
            raise
        except httpx.HTTPError as exc:
            raise GitOpsProviderError(f"GitHub API request failed: {exc}") from exc
        finally:
            if owns_client:
                client.close()

    def _default_branch_sha(self, client: httpx.Client) -> str:
        response = client.get(
            f"/repos/{self._owner}/{self._repo}/git/ref/heads/{self._base_branch}"
        )
        if response.status_code >= 400:
            raise GitOpsProviderError(
                f"failed to resolve base branch {self._base_branch}: "
                f"HTTP {response.status_code} {response.text[:200]}"
            )
        payload = response.json()
        sha = ((payload.get("object") or {}).get("sha")) or ""
        if not sha:
            raise GitOpsProviderError("base branch SHA missing")
        return str(sha)

    def _ensure_branch(self, client: httpx.Client, *, branch: str, sha: str) -> None:
        existing = client.get(
            f"/repos/{self._owner}/{self._repo}/git/ref/heads/{branch}"
        )
        if existing.status_code == 200:
            return
        response = client.post(
            f"/repos/{self._owner}/{self._repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": sha},
        )
        if response.status_code >= 400:
            raise GitOpsProviderError(
                f"failed to create branch {branch}: "
                f"HTTP {response.status_code} {response.text[:200]}"
            )

    def _put_file(
        self,
        client: httpx.Client,
        *,
        path: str,
        content: str,
        branch: str,
        message: str,
    ) -> None:
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        payload: dict[str, Any] = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        # Update if the note already exists on the branch.
        current = client.get(
            f"/repos/{self._owner}/{self._repo}/contents/{path}",
            params={"ref": branch},
        )
        if current.status_code == 200:
            sha = current.json().get("sha")
            if sha:
                payload["sha"] = sha
        response = client.put(
            f"/repos/{self._owner}/{self._repo}/contents/{path}",
            json=payload,
        )
        if response.status_code >= 400:
            raise GitOpsProviderError(
                f"failed to commit remediation note: "
                f"HTTP {response.status_code} {response.text[:200]}"
            )

    def _create_pull_request(
        self,
        client: httpx.Client,
        *,
        title: str,
        body: str,
        head: str,
    ) -> dict[str, Any]:
        response = client.post(
            f"/repos/{self._owner}/{self._repo}/pulls",
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": self._base_branch,
                "draft": self._draft,
            },
        )
        if response.status_code >= 400:
            raise GitOpsProviderError(
                f"failed to create pull request: "
                f"HTTP {response.status_code} {response.text[:200]}"
            )
        data = response.json()
        if not isinstance(data, dict):
            raise GitOpsProviderError("unexpected GitHub pulls response")
        return data


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def resolve_gitops_provider_name() -> str:
    explicit = os.getenv("GITOPS_PROVIDER", "").strip().lower()
    if explicit in {"noop", "null", "none"}:
        return "noop"
    if explicit == "github":
        return "github"
    token = os.getenv("GITHUB_TOKEN", "").strip()
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if token and repo:
        return "github"
    return "noop"


def build_gitops_provider(
    *,
    client: httpx.Client | None = None,
) -> GitOpsProvider:
    name = resolve_gitops_provider_name()
    if name != "github":
        return NullGitOpsProvider()
    token = os.getenv("GITHUB_TOKEN", "").strip()
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not token or not repo:
        raise GitOpsProviderError(
            "GITOPS_PROVIDER=github requires GITHUB_TOKEN and GITHUB_REPOSITORY"
        )
    return GitHubPullRequestProvider(
        token=token,
        repository=repo,
        api_url=os.getenv("GITHUB_API_URL", "https://api.github.com").strip()
        or "https://api.github.com",
        base_branch=os.getenv("GITHUB_BASE_BRANCH", "main").strip() or "main",
        draft=_env_bool("GITHUB_PR_DRAFT", True),
        client=client,
    )


def get_gitops_provider() -> GitOpsProvider:
    global _provider
    if _provider is not None:
        return _provider
    with _provider_lock:
        if _provider is None:
            _provider = build_gitops_provider()
    return _provider


def reset_gitops_provider(provider: GitOpsProvider | None = None) -> None:
    global _provider
    with _provider_lock:
        _provider = provider
