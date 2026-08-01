"""Load and cache a validated governance policy bundle."""

from __future__ import annotations

import hashlib
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Literal

from app.governance_service import get_governance_root, load_module

ValidationStatus = Literal["ok", "error"]

# YAML files that contribute to the content digest and runtime configs.
_POLICY_YAML_RELATIVE = (
    Path("policy-packs") / "packs.yaml",
    Path("quota") / "policies.yaml",
    Path("registry") / "models.yaml",
    Path("sovereign") / "residency.yaml",
    Path("agents") / "agents.yaml",
    Path("tools") / "tools.yaml",
    Path("cost") / "policies.yaml",
    Path("risk") / "rules.yaml",
)

_bundle: PolicyBundle | None = None
_lock = threading.Lock()


def _git_revision() -> str:
    for key in ("GIT_COMMIT", "SOURCE_COMMIT"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    return "unknown"


def _content_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for relative in _POLICY_YAML_RELATIVE:
        path = root / relative
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        if path.is_file():
            digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass
class PolicyBundle:
    """In-memory snapshot of governance modules and parsed configs."""

    bundle_id: str
    git_revision: str
    content_digest: str
    loaded_at: str
    validation_status: ValidationStatus
    packs: Any = None
    quota_policies: Any = None
    registry: Any = None
    residency: Any = None
    agents: Any = None
    tools: Any = None
    cost_policies: Any = None
    risk_rules: Any = None
    pack_module: ModuleType | None = None
    quota_module: ModuleType | None = None
    registry_module: ModuleType | None = None
    sovereign_module: ModuleType | None = None
    agent_module: ModuleType | None = None
    tools_module: ModuleType | None = None
    cost_module: ModuleType | None = None
    risk_module: ModuleType | None = None
    approval_module: ModuleType | None = None
    prompt_module: ModuleType | None = None
    error: str | None = None
    modules: dict[str, ModuleType] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path) -> PolicyBundle:
        """Load modules and parse policy YAML under ``root``."""
        loaded_at = datetime.now(UTC).isoformat()
        git_revision = _git_revision()
        content_digest = _content_digest(root)
        bundle_id = content_digest[:12]

        try:
            pack_module = load_module(
                "policy_packs_bundle", root / "policy-packs" / "evaluate.py"
            )
            quota_module = load_module(
                "quota_governance_bundle", root / "quota" / "evaluate.py"
            )
            registry_module = load_module(
                "model_registry_bundle", root / "registry" / "evaluate.py"
            )
            sovereign_module = load_module(
                "sovereign_ai_bundle", root / "sovereign" / "evaluate.py"
            )
            agent_module = load_module(
                "agent_registry_bundle", root / "agents" / "evaluate.py"
            )
            tools_module = load_module(
                "tool_registry_bundle", root / "tools" / "evaluate.py"
            )
            cost_module = load_module(
                "cost_governance_bundle", root / "cost" / "evaluate.py"
            )
            risk_module = load_module(
                "risk_governance_bundle", root / "risk" / "evaluate.py"
            )
            approval_module = load_module(
                "approval_governance_bundle", root / "approval" / "evaluate.py"
            )
            prompt_module = load_module(
                "prompt_security_bundle", root / "prompt-security" / "evaluate.py"
            )

            packs = pack_module.parse_packs(root / "policy-packs" / "packs.yaml")
            quota_policies = quota_module.parse_policies(
                root / "quota" / "policies.yaml"
            )
            registry = registry_module.parse_registry(
                root / "registry" / "models.yaml"
            )
            residency = sovereign_module.parse_residency(
                root / "sovereign" / "residency.yaml"
            )
            agents = agent_module.parse_registry(root / "agents" / "agents.yaml")
            tools = tools_module.parse_registry(root / "tools" / "tools.yaml")
            cost_policies = cost_module.parse_policy_file(
                root / "cost" / "policies.yaml"
            )
            risk_rules = risk_module.parse_rules(root / "risk" / "rules.yaml")

            modules = {
                "packs": pack_module,
                "quota": quota_module,
                "registry": registry_module,
                "sovereign": sovereign_module,
                "agents": agent_module,
                "tools": tools_module,
                "cost": cost_module,
                "risk": risk_module,
                "approval": approval_module,
                "prompt": prompt_module,
            }
            return cls(
                bundle_id=bundle_id,
                git_revision=git_revision,
                content_digest=content_digest,
                loaded_at=loaded_at,
                validation_status="ok",
                packs=packs,
                quota_policies=quota_policies,
                registry=registry,
                residency=residency,
                agents=agents,
                tools=tools,
                cost_policies=cost_policies,
                risk_rules=risk_rules,
                pack_module=pack_module,
                quota_module=quota_module,
                registry_module=registry_module,
                sovereign_module=sovereign_module,
                agent_module=agent_module,
                tools_module=tools_module,
                cost_module=cost_module,
                risk_module=risk_module,
                approval_module=approval_module,
                prompt_module=prompt_module,
                modules=modules,
            )
        except Exception as exc:  # noqa: BLE001 - surface load failures in bundle
            return cls(
                bundle_id=str(uuid.uuid4()),
                git_revision=git_revision,
                content_digest=content_digest,
                loaded_at=loaded_at,
                validation_status="error",
                error=str(exc),
            )


def get_policy_bundle(*, root: Path | None = None) -> PolicyBundle:
    """Return the process-wide policy bundle, loading it on first use."""
    global _bundle
    if _bundle is not None:
        return _bundle

    with _lock:
        if _bundle is None:
            load_root = root if root is not None else get_governance_root()
            _bundle = PolicyBundle.load(load_root)
    return _bundle


def reload_policy_bundle(*, root: Path | None = None) -> PolicyBundle:
    """Force-reload the process-wide policy bundle."""
    global _bundle
    with _lock:
        load_root = root if root is not None else get_governance_root()
        _bundle = PolicyBundle.load(load_root)
        return _bundle


def clear_policy_bundle() -> None:
    """Clear the cached policy bundle (tests)."""
    global _bundle
    with _lock:
        _bundle = None
