"""Suggested remediation actions for inventory drift (no auto-apply)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.drift_service import DriftStatus


class DriftSuggestedAction(BaseModel):
    kind: Literal[
        "pull_model",
        "update_inventory",
        "open_github_issue",
        "open_github_pr",
        "reprobe",
    ]
    title: str
    description: str
    backend: str | None = None
    model: str | None = None
    command: str | None = None
    issue_title: str | None = None
    issue_body: str | None = None
    pr_title: str | None = None
    pr_body: str | None = None


class DriftActionsResponse(BaseModel):
    in_sync: bool
    summary: str
    actions: list[DriftSuggestedAction] = Field(default_factory=list)


def build_drift_actions(status: DriftStatus) -> DriftActionsResponse:
    actions: list[DriftSuggestedAction] = []
    if status.in_sync:
        return DriftActionsResponse(
            in_sync=True,
            summary=status.summary,
            actions=[],
        )

    for backend in status.backends:
        if not backend.probe_healthy:
            actions.append(
                DriftSuggestedAction(
                    kind="reprobe",
                    title=f"Restore {backend.backend} probe connectivity",
                    description=(
                        f"{backend.backend} probe failed"
                        + (
                            f": {backend.probe_error}"
                            if backend.probe_error
                            else ""
                        )
                    ),
                    backend=backend.backend,
                    command=(
                        "curl -fsS \"$OLLAMA_BASE_URL/api/tags\""
                        if backend.backend == "ollama"
                        else "curl -fsS \"$VLLM_BASE_URL/v1/models\""
                    ),
                )
            )
            continue

        for model in backend.missing_on_backend:
            if backend.backend == "ollama":
                command = f"ollama pull {model}"
            else:
                command = (
                    f"# ensure vLLM serves '{model}' or remove it from inventory"
                )
            actions.append(
                DriftSuggestedAction(
                    kind="pull_model",
                    title=f"Provision missing model {model}",
                    description=(
                        f"Inventory expects {model} on {backend.backend}, "
                        "but the live probe does not expose it."
                    ),
                    backend=backend.backend,
                    model=model,
                    command=command,
                )
            )

        for model in backend.unexpected_on_backend:
            actions.append(
                DriftSuggestedAction(
                    kind="update_inventory",
                    title=f"Reconcile unexpected model {model}",
                    description=(
                        f"{backend.backend} exposes {model}, which is not in "
                        "configured inventory. Add it to MODEL_INVENTORY or unload it."
                    ),
                    backend=backend.backend,
                    model=model,
                    command=(
                        "# edit fleet/model inventory ConfigMap / MODEL_INVENTORY_PATH"
                    ),
                )
            )

    missing = [
        f"{b.backend}:{m}" for b in status.backends for m in b.missing_on_backend
    ]
    unexpected = [
        f"{b.backend}:{m}" for b in status.backends for m in b.unexpected_on_backend
    ]
    issue_body = (
        "## Inventory drift detected\n\n"
        f"**Summary:** {status.summary}\n\n"
        f"**Missing on backend:** {', '.join(missing) or 'none'}\n"
        f"**Unexpected on backend:** {', '.join(unexpected) or 'none'}\n\n"
        "### Suggested next steps\n"
        "1. Confirm probe health for Ollama/vLLM.\n"
        "2. Pull or unload models, or update inventory.\n"
        "3. Re-check `GET /drift` until `in_sync=true`.\n"
    )
    actions.append(
        DriftSuggestedAction(
            kind="open_github_issue",
            title="Open GitHub issue for drift",
            description="Track remediation with operators via GitOps issue.",
            issue_title=f"Inventory drift: {status.summary}",
            issue_body=issue_body,
        )
    )
    actions.append(
        DriftSuggestedAction(
            kind="open_github_pr",
            title="Open inventory reconciliation PR",
            description=(
                "Propose inventory ConfigMap changes when unexpected models "
                "should become desired state."
            ),
            pr_title="fix: reconcile model inventory with live probes",
            pr_body=(
                "## Why\n\n"
                f"{status.summary}\n\n"
                "## Changes\n\n"
                "- Update model inventory to match approved live backends\n"
                "- Or document intentional removals\n\n"
                "## Validation\n\n"
                "- [ ] `GET /drift` returns `in_sync: true`\n"
            ),
        )
    )

    return DriftActionsResponse(
        in_sync=False,
        summary=status.summary,
        actions=actions,
    )
