"""Signed model registry catalog and attestation status API."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.governance_service import get_governance_root, load_module


class ModelRegistryEntry(BaseModel):
    name: str
    revision: str | None = None
    artifact_digest: str | None = None
    sbom_ref: str | None = None
    license: str | None = None
    risk_tier: str | None = None
    allowed_namespaces: list[str] = Field(default_factory=list)
    allowed_teams: list[str] = Field(default_factory=list)
    forbidden: bool = False
    external_provider: bool = False
    has_attestation_signature: bool = False
    attestation_verified: bool | None = None
    attestation_status: Literal["verified", "unsigned", "invalid", "not_required"] = (
        "not_required"
    )


class ModelRegistryResponse(BaseModel):
    updated_at: str
    signature_verify_enabled: bool
    model_count: int
    models: list[ModelRegistryEntry] = Field(default_factory=list)


def _load_signing_module():
    path = get_governance_root() / "registry" / "signing.py"
    spec = importlib.util.spec_from_file_location("registry_signing_api", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load signing module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _attestation_status_label(
    entry: dict[str, Any],
    *,
    verified: bool | None,
    verify_enabled: bool,
) -> Literal["verified", "unsigned", "invalid", "not_required"]:
    if not verify_enabled:
        return "verified" if verified else "not_required"
    if not entry.get("artifact_digest"):
        return "not_required"
    if not entry.get("attestation_signature"):
        return "unsigned"
    if verified:
        return "verified"
    return "invalid"


def build_model_registry() -> ModelRegistryResponse:
    root = get_governance_root()
    registry_module = load_module("model_registry_api", root / "registry" / "evaluate.py")
    signing = _load_signing_module()
    registry = registry_module.parse_registry(root / "registry" / "models.yaml")
    verify_enabled = signing.is_registry_signature_verify_enabled()

    models: list[ModelRegistryEntry] = []
    for name in sorted(registry):
        entry = registry[name]
        attestation = signing.attestation_status(name, entry)
        verified = attestation.get("attestation_verified")
        models.append(
            ModelRegistryEntry(
                name=name,
                revision=entry.get("revision"),
                artifact_digest=entry.get("artifact_digest"),
                sbom_ref=entry.get("sbom_ref"),
                license=entry.get("license"),
                risk_tier=entry.get("risk_tier"),
                allowed_namespaces=list(entry.get("allowed_namespaces", [])),
                allowed_teams=list(entry.get("allowed_teams", [])),
                forbidden=bool(entry.get("forbidden", False)),
                external_provider=bool(entry.get("external_provider", False)),
                has_attestation_signature=bool(attestation["has_attestation_signature"]),
                attestation_verified=verified,
                attestation_status=_attestation_status_label(
                    entry,
                    verified=verified if isinstance(verified, bool) else None,
                    verify_enabled=verify_enabled,
                ),
            )
        )

    return ModelRegistryResponse(
        updated_at=datetime.now(UTC).isoformat(),
        signature_verify_enabled=verify_enabled,
        model_count=len(models),
        models=models,
    )


def get_model_registry_entry(model_name: str) -> ModelRegistryEntry | None:
    response = build_model_registry()
    for entry in response.models:
        if entry.name == model_name:
            return entry
    return None
