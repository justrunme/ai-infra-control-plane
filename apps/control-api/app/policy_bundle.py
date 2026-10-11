"""Load and cache a validated governance policy bundle.

Bundle content is treated as **data-only** (YAML/policy packs). Evaluation
engines (``evaluate.py``) are loaded from the control-plane shipped governance
tree, not from an OCI-fetched path, so a compromised registry cannot execute
arbitrary Python inside the API process.

Set ``POLICY_BUNDLE_ALLOW_EXECUTABLE=true`` only for local experiments that
intentionally load ``evaluate.py`` from the materialized bundle root.
"""

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
    Path("cost") / "pricing.yaml",
    Path("risk") / "rules.yaml",
    Path("classification") / "tenants.yaml",
)

_ENGINE_MODULES = (
    ("packs", "policy_packs_bundle", Path("policy-packs") / "evaluate.py"),
    ("quota", "quota_governance_bundle", Path("quota") / "evaluate.py"),
    ("registry", "model_registry_bundle", Path("registry") / "evaluate.py"),
    ("sovereign", "sovereign_ai_bundle", Path("sovereign") / "evaluate.py"),
    ("agents", "agent_registry_bundle", Path("agents") / "evaluate.py"),
    ("tools", "tool_registry_bundle", Path("tools") / "evaluate.py"),
    ("cost", "cost_governance_bundle", Path("cost") / "evaluate.py"),
    ("risk", "risk_governance_bundle", Path("risk") / "evaluate.py"),
    ("approval", "approval_governance_bundle", Path("approval") / "evaluate.py"),
    ("prompt", "prompt_security_bundle", Path("prompt-security") / "evaluate.py"),
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


def _allow_executable_bundle() -> bool:
    return os.getenv("POLICY_BUNDLE_ALLOW_EXECUTABLE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _engine_root(data_root: Path) -> Path:
    """Return the trusted root for evaluate.py modules."""
    if _allow_executable_bundle():
        return data_root
    shipped = get_governance_root()
    if shipped.is_dir():
        return shipped
    return data_root


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
    engine_root: str = ""
    data_root: str = ""

    @classmethod
    def load(cls, root: Path) -> PolicyBundle:
        """Load trusted engines and parse policy YAML under ``root``."""
        loaded_at = datetime.now(UTC).isoformat()
        git_revision = _git_revision()
        content_digest = _content_digest(root)
        bundle_id = content_digest[:12]
        data_root = root
        engine_root = _engine_root(root)

        try:
            loaded: dict[str, ModuleType] = {}
            for key, module_name, relative in _ENGINE_MODULES:
                path = engine_root / relative
                if not path.is_file():
                    raise FileNotFoundError(
                        f"trusted policy engine missing: {path}"
                    )
                loaded[key] = load_module(module_name, path)

            pack_module = loaded["packs"]
            quota_module = loaded["quota"]
            registry_module = loaded["registry"]
            sovereign_module = loaded["sovereign"]
            agent_module = loaded["agents"]
            tools_module = loaded["tools"]
            cost_module = loaded["cost"]
            risk_module = loaded["risk"]
            approval_module = loaded["approval"]
            prompt_module = loaded["prompt"]

            packs = pack_module.parse_packs(data_root / "policy-packs" / "packs.yaml")
            quota_policies = quota_module.parse_policies(
                data_root / "quota" / "policies.yaml"
            )
            registry = registry_module.parse_registry(
                data_root / "registry" / "models.yaml"
            )
            residency = sovereign_module.parse_residency(
                data_root / "sovereign" / "residency.yaml"
            )
            agents = agent_module.parse_registry(data_root / "agents" / "agents.yaml")
            tools = tools_module.parse_registry(data_root / "tools" / "tools.yaml")
            cost_policies = cost_module.parse_policy_file(
                data_root / "cost" / "policies.yaml"
            )
            risk_rules = risk_module.parse_rules(data_root / "risk" / "rules.yaml")

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
                modules=loaded,
                engine_root=str(engine_root),
                data_root=str(data_root),
            )
        except Exception as exc:  # noqa: BLE001 - surface load failures in bundle
            return cls(
                bundle_id=str(uuid.uuid4()),
                git_revision=git_revision,
                content_digest=content_digest,
                loaded_at=loaded_at,
                validation_status="error",
                error=str(exc),
                engine_root=str(engine_root),
                data_root=str(data_root),
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
