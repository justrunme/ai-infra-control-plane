"""Runtime verification contract for remediation closed-loop (v2.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.drift_service import DriftStatus

SCHEMA_VERSION = "runtime-verification/2.3"

CheckName = Literal[
    "inventory_drift",
    "baseline_closure",
    "probe_freshness",
]
CheckStatus = Literal["pass", "fail", "skipped"]
VerifyOutcome = Literal["verified", "failed"]


class VerificationCheck(BaseModel):
    name: CheckName
    status: CheckStatus
    detail: str = ""


class BaselineClosure(BaseModel):
    baseline_missing: list[str] = Field(default_factory=list)
    still_missing: list[str] = Field(default_factory=list)
    resolved: list[str] = Field(default_factory=list)
    closed: bool = True


class RuntimeVerificationSnapshot(BaseModel):
    schema_version: Literal["runtime-verification/2.3"] = SCHEMA_VERSION
    verified_at: str
    proposal_id: str
    outcome: VerifyOutcome
    inventory: DriftStatus
    checks: list[VerificationCheck] = Field(default_factory=list)
    baseline_closure: BaselineClosure | None = None
    gitops_sync: Literal["not_checked"] = "not_checked"

    def to_persist_dict(self) -> dict[str, Any]:
        """Persist envelope plus legacy DriftStatus top-level aliases."""
        payload = self.model_dump()
        inventory = payload.get("inventory") or {}
        if isinstance(inventory, dict):
            # Dual-write for clients that still expect raw DriftStatus fields.
            for key in ("updated_at", "in_sync", "summary", "backends"):
                if key in inventory:
                    payload[key] = inventory[key]
        return payload


def _missing_from_drift_snapshot(snapshot: dict[str, Any] | None) -> list[str]:
    if not snapshot:
        return []
    missing: list[str] = []
    backends = snapshot.get("backends") or []
    if isinstance(backends, list):
        for backend in backends:
            if not isinstance(backend, dict):
                continue
            for name in backend.get("missing_on_backend") or []:
                if name and name not in missing:
                    missing.append(str(name))
    return missing


def _missing_from_status(status: DriftStatus) -> list[str]:
    missing: list[str] = []
    for backend in status.backends:
        for name in backend.missing_on_backend:
            if name and name not in missing:
                missing.append(name)
    return missing


def build_baseline_closure(
    *,
    baseline_snapshot: dict[str, Any] | None,
    current: DriftStatus,
) -> BaselineClosure:
    baseline_missing = _missing_from_drift_snapshot(baseline_snapshot)
    current_missing = set(_missing_from_status(current))
    still_missing = [name for name in baseline_missing if name in current_missing]
    resolved = [name for name in baseline_missing if name not in current_missing]
    if not baseline_missing:
        return BaselineClosure(closed=True)
    return BaselineClosure(
        baseline_missing=baseline_missing,
        still_missing=still_missing,
        resolved=resolved,
        closed=not still_missing,
    )


def build_verification_snapshot(
    *,
    proposal_id: str,
    inventory: DriftStatus,
    baseline_snapshot: dict[str, Any] | None,
    probe_fresh: bool = True,
) -> RuntimeVerificationSnapshot:
    checks: list[VerificationCheck] = [
        VerificationCheck(
            name="probe_freshness",
            status="pass" if probe_fresh else "skipped",
            detail="fresh probes" if probe_fresh else "injected drift fixture",
        )
    ]
    checks.append(
        VerificationCheck(
            name="inventory_drift",
            status="pass" if inventory.in_sync else "fail",
            detail=inventory.summary or (
                "inventory in sync" if inventory.in_sync else "inventory drifting"
            ),
        )
    )
    closure = build_baseline_closure(
        baseline_snapshot=baseline_snapshot,
        current=inventory,
    )
    baseline_missing = closure.baseline_missing
    if not baseline_missing:
        checks.append(
            VerificationCheck(
                name="baseline_closure",
                status="skipped",
                detail="no baseline missing models",
            )
        )
    else:
        checks.append(
            VerificationCheck(
                name="baseline_closure",
                status="pass" if closure.closed else "fail",
                detail=(
                    "baseline missing models resolved"
                    if closure.closed
                    else f"still missing: {', '.join(closure.still_missing)}"
                ),
            )
        )

    failed = [check for check in checks if check.status == "fail"]
    outcome: VerifyOutcome = "failed" if failed else "verified"
    return RuntimeVerificationSnapshot(
        verified_at=datetime.now(UTC).isoformat(),
        proposal_id=proposal_id,
        outcome=outcome,
        inventory=inventory,
        checks=checks,
        baseline_closure=closure,
        gitops_sync="not_checked",
    )
