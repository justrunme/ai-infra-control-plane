"""Resolve policy bundle content from filesystem or OCI sources."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PolicySource:
    type: str  # filesystem | oci
    path: str = ""
    reference: str = ""
    digest: str = ""
    verify_signature: bool = False


def policy_source_from_env() -> PolicySource:
    source_type = os.getenv("POLICY_SOURCE_TYPE", "filesystem").strip().lower()
    return PolicySource(
        type=source_type or "filesystem",
        path=os.getenv("POLICY_SOURCE_PATH", "").strip(),
        reference=os.getenv("POLICY_SOURCE_OCI_REF", "").strip(),
        digest=os.getenv("POLICY_SOURCE_OCI_DIGEST", "").strip(),
        verify_signature=os.getenv("POLICY_SOURCE_VERIFY_SIGNATURE", "").strip().lower()
        in {"1", "true", "yes", "on"},
    )


def materialize_policy_root(
    source: PolicySource,
    *,
    default_root: Path,
) -> Path:
    """Return a local directory containing a loadable governance tree."""
    if source.type in {"", "filesystem"}:
        if source.path:
            root = Path(source.path).expanduser().resolve()
        else:
            root = default_root
        if not root.is_dir():
            raise FileNotFoundError(f"policy filesystem root not found: {root}")
        return root

    if source.type != "oci":
        raise ValueError(f"unsupported POLICY_SOURCE_TYPE: {source.type}")

    if not source.reference:
        raise ValueError("POLICY_SOURCE_OCI_REF is required for oci policy source")

    if source.verify_signature:
        _cosign_verify_oci(source.reference, digest=source.digest)

    pull_ref = source.reference
    if source.digest and "@" not in pull_ref:
        # Prefer digest pin when provided separately.
        repo = pull_ref.split(":", 1)[0]
        pull_ref = f"{repo}@{source.digest}"

    target = Path(tempfile.mkdtemp(prefix="ai-policy-oci-"))
    _oras_pull(pull_ref, target)
    # Accept either a governance/ layout or flat policy files at root.
    if (target / "governance").is_dir():
        return target / "governance"
    if (target / "policy-packs").is_dir():
        return target
    raise FileNotFoundError(
        f"OCI policy artifact {pull_ref} missing governance/ or policy-packs/"
    )


def _oras_pull(reference: str, target: Path) -> None:
    if shutil.which("oras") is None:
        raise RuntimeError(
            "oras CLI is required to pull OCI policy bundles "
            "(install oras or use POLICY_SOURCE_TYPE=filesystem)"
        )
    subprocess.run(
        ["oras", "pull", reference, "-o", str(target)],
        check=True,
        capture_output=True,
        text=True,
    )


def _cosign_verify_oci(reference: str, *, digest: str = "") -> None:
    if shutil.which("cosign") is None:
        raise RuntimeError(
            "cosign CLI is required when POLICY_SOURCE_VERIFY_SIGNATURE=true"
        )
    ref = reference
    if digest and "@" not in ref:
        ref = f"{ref.split(':', 1)[0]}@{digest}"
    identity_re = os.getenv(
        "POLICY_SOURCE_COSIGN_IDENTITY_REGEXP",
        r"https://github.com/.*/\.github/workflows/.*",
    )
    issuer = os.getenv(
        "POLICY_SOURCE_COSIGN_OIDC_ISSUER",
        "https://token.actions.githubusercontent.com",
    )
    subprocess.run(
        [
            "cosign",
            "verify",
            "--certificate-identity-regexp",
            identity_re,
            "--certificate-oidc-issuer",
            issuer,
            ref,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
