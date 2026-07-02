"""HMAC attestation helpers for signed model registry entries."""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

CANONICAL_FIELDS = ("revision", "artifact_digest", "risk_tier", "license")
DEFAULT_DEMO_SIGNING_KEY = "ai-platform-registry-demo"


def get_signing_key() -> str:
    return os.getenv("MODEL_REGISTRY_SIGNING_KEY", DEFAULT_DEMO_SIGNING_KEY).strip()


def is_registry_signature_verify_enabled() -> bool:
    return os.getenv("MODEL_REGISTRY_VERIFY", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def canonical_payload(model: str, entry: dict[str, Any]) -> str:
    parts = [model]
    for field in CANONICAL_FIELDS:
        parts.append(str(entry.get(field, "")))
    return "|".join(parts)


def sign_entry(model: str, entry: dict[str, Any], secret: str | None = None) -> str:
    key = secret if secret is not None else get_signing_key()
    return hmac.new(
        key.encode(),
        canonical_payload(model, entry).encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_entry_signature(
    model: str,
    entry: dict[str, Any],
    secret: str | None = None,
) -> bool:
    stored = str(entry.get("attestation_signature", "")).strip()
    if not stored:
        return False
    return hmac.compare_digest(stored, sign_entry(model, entry, secret=secret))


def attestation_status(model: str, entry: dict[str, Any]) -> dict[str, Any]:
    has_signature = bool(str(entry.get("attestation_signature", "")).strip())
    verified = verify_entry_signature(model, entry) if has_signature else None
    return {
        "has_attestation_signature": has_signature,
        "attestation_verified": verified,
        "artifact_digest": entry.get("artifact_digest"),
        "revision": entry.get("revision"),
        "license": entry.get("license"),
    }
