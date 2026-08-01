"""Policy bundle validation, simulation, activation, and rollback."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.decision_store import DecisionStore, get_decision_store
from app.governance_service import (
    GovernanceEvaluateRequest,
    evaluate_governance_request,
    get_governance_root,
)
from app.policy_bundle import (
    PolicyBundle,
    get_policy_bundle,
    reload_policy_bundle,
)
from app.policy_source import (
    PolicySource,
    materialize_policy_root,
    policy_source_from_env,
)


@dataclass
class BundleImpact:
    bundle_id: str
    content_digest: str
    evaluated_decisions: int = 0
    unchanged: int = 0
    allow_to_block: int = 0
    allow_to_approval: int = 0
    block_to_allow: int = 0
    approval_to_allow: int = 0
    approval_to_block: int = 0
    other_changes: int = 0
    sample_changes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "content_digest": self.content_digest,
            "evaluated_decisions": self.evaluated_decisions,
            "unchanged": self.unchanged,
            "allow_to_block": self.allow_to_block,
            "allow_to_approval": self.allow_to_approval,
            "block_to_allow": self.block_to_allow,
            "approval_to_allow": self.approval_to_allow,
            "approval_to_block": self.approval_to_block,
            "other_changes": self.other_changes,
            "sample_changes": self.sample_changes[:20],
        }


class PolicyLifecycle:
    """Process-local candidate registry with last-known-good rollback."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._candidates: dict[str, PolicyBundle] = {}
        self._previous: PolicyBundle | None = None
        self._impacts: dict[str, BundleImpact] = {}
        self._active_source: PolicySource = policy_source_from_env()

    def active(self) -> PolicyBundle:
        return get_policy_bundle()

    def previous(self) -> PolicyBundle | None:
        with self._lock:
            return self._previous

    def list_candidates(self) -> list[PolicyBundle]:
        with self._lock:
            return list(self._candidates.values())

    def get_candidate(self, bundle_id: str) -> PolicyBundle | None:
        with self._lock:
            if bundle_id in self._candidates:
                return self._candidates[bundle_id]
            active = get_policy_bundle()
            if active.bundle_id == bundle_id:
                return active
            if self._previous and self._previous.bundle_id == bundle_id:
                return self._previous
            return None

    def validate_from_path(self, root: Path) -> PolicyBundle:
        bundle = PolicyBundle.load(root)
        if bundle.validation_status != "ok":
            return bundle
        with self._lock:
            self._candidates[bundle.bundle_id] = bundle
        return bundle

    def validate_from_source(self, source: PolicySource | None = None) -> PolicyBundle:
        source = source or policy_source_from_env()
        root = materialize_policy_root(source, default_root=get_governance_root())
        bundle = self.validate_from_path(root)
        with self._lock:
            self._active_source = source
        return bundle

    def ensure_bootstrapped(self) -> PolicyBundle:
        """Load active bundle from configured source; keep last-known-good on failure."""
        with self._lock:
            current = get_policy_bundle()
            try:
                source = policy_source_from_env()
                root = materialize_policy_root(
                    source, default_root=get_governance_root()
                )
                loaded = PolicyBundle.load(root)
                if loaded.validation_status != "ok":
                    if current.validation_status == "ok":
                        return current
                    raise RuntimeError(loaded.error or "policy bundle invalid")
                if current.validation_status == "ok" and current.content_digest != (
                    loaded.content_digest
                ):
                    self._previous = current
                reload_policy_bundle(root=root)
                self._active_source = source
                return get_policy_bundle()
            except Exception:
                if current.validation_status == "ok":
                    return current
                raise

    def simulate(
        self,
        bundle_id: str,
        *,
        limit: int = 200,
        store: DecisionStore | None = None,
    ) -> BundleImpact:
        candidate = self.get_candidate(bundle_id)
        if candidate is None or candidate.validation_status != "ok":
            raise KeyError(f"validated policy bundle not found: {bundle_id}")

        decision_store = store or get_decision_store()
        records = decision_store.list_recent_decisions(limit=limit)
        impact = BundleImpact(
            bundle_id=candidate.bundle_id,
            content_digest=candidate.content_digest,
        )
        for record in records:
            if not record.request:
                continue
            try:
                request = GovernanceEvaluateRequest.model_validate(record.request)
                result = evaluate_governance_request(request, bundle=candidate)
            except Exception:  # noqa: BLE001
                impact.other_changes += 1
                continue
            impact.evaluated_decisions += 1
            before = record.final_verdict
            after = result.final_verdict
            if before == after:
                impact.unchanged += 1
                continue
            key = f"{before}->{after}"
            if key == "allow->block":
                impact.allow_to_block += 1
            elif key == "allow->approval_required":
                impact.allow_to_approval += 1
            elif key == "block->allow":
                impact.block_to_allow += 1
            elif key == "approval_required->allow":
                impact.approval_to_allow += 1
            elif key == "approval_required->block":
                impact.approval_to_block += 1
            else:
                impact.other_changes += 1
            if len(impact.sample_changes) < 20:
                impact.sample_changes.append(
                    {
                        "decision_id": record.decision_id,
                        "before": before,
                        "after": after,
                        "team": record.team,
                        "model": record.model,
                    }
                )
        with self._lock:
            self._impacts[bundle_id] = impact
        return impact

    def impact(self, bundle_id: str) -> BundleImpact | None:
        with self._lock:
            return self._impacts.get(bundle_id)

    def activate(self, bundle_id: str) -> PolicyBundle:
        with self._lock:
            candidate = self._candidates.get(bundle_id)
            if candidate is None or candidate.validation_status != "ok":
                raise KeyError(f"validated policy bundle not found: {bundle_id}")
            current = get_policy_bundle()
            if current.validation_status == "ok":
                self._previous = current
            # Replace process-wide active bundle.
            from app import policy_bundle as pb

            with pb._lock:
                pb._bundle = candidate
            return candidate

    def rollback(self) -> PolicyBundle:
        with self._lock:
            if self._previous is None or self._previous.validation_status != "ok":
                raise RuntimeError("no last-known-good policy bundle to rollback to")
            current = get_policy_bundle()
            previous = self._previous
            self._previous = (
                current if current.validation_status == "ok" else self._previous
            )
            from app import policy_bundle as pb

            with pb._lock:
                pb._bundle = previous
            return previous


_lifecycle: PolicyLifecycle | None = None
_lifecycle_lock = threading.Lock()


def get_policy_lifecycle() -> PolicyLifecycle:
    global _lifecycle
    if _lifecycle is None:
        with _lifecycle_lock:
            if _lifecycle is None:
                _lifecycle = PolicyLifecycle()
    return _lifecycle


def reset_policy_lifecycle() -> None:
    global _lifecycle
    with _lifecycle_lock:
        _lifecycle = None
