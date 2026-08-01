"""Policy bundle validation, simulation, activation, and rollback.

Active selection is durable (monotonic ``generation`` in the decision store).
Replicas catch up via ``sync_active_from_store``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.decision_store import DecisionStore, PolicyBundleRecord, get_decision_store
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
    get_policy_failure_mode,
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


def _source_to_json(source: PolicySource) -> dict[str, Any]:
    return {
        "type": source.type,
        "path": source.path,
        "reference": source.reference,
        "digest": source.digest,
        "verify_signature": source.verify_signature,
    }


def _source_from_json(payload: dict[str, Any]) -> PolicySource:
    return PolicySource(
        type=str(payload.get("type") or "filesystem"),
        path=str(payload.get("path") or ""),
        reference=str(payload.get("reference") or ""),
        digest=str(payload.get("digest") or ""),
        verify_signature=bool(payload.get("verify_signature")),
    )


class PolicyLifecycle:
    """Durable PolicyBundle lifecycle with per-process hot cache."""

    def __init__(self, store: DecisionStore | None = None) -> None:
        self._lock = threading.RLock()
        self._store = store
        self._candidates: dict[str, PolicyBundle] = {}
        self._candidate_sources: dict[str, dict[str, Any]] = {}
        self._previous: PolicyBundle | None = None
        self._impacts: dict[str, BundleImpact] = {}
        self._active_source: PolicySource = policy_source_from_env()
        self._bootstrap_error: str | None = None
        self._fallback_active: bool = False
        self._expected_digest: str = ""
        self._observed_digest: str = ""
        self._observed_generation: int = 0
        self._active_generation: int = 0

    def _decision_store(self) -> DecisionStore:
        return self._store or get_decision_store()

    def active(self) -> PolicyBundle:
        self.sync_active_from_store()
        return get_policy_bundle()

    def previous(self) -> PolicyBundle | None:
        with self._lock:
            if self._previous is not None:
                return self._previous
        store = self._decision_store()
        record = store.get_previous_policy_bundle()
        if record is None:
            return None
        try:
            return self._load_from_record(record)
        except Exception:  # noqa: BLE001
            return None

    def list_candidates(self) -> list[PolicyBundle]:
        with self._lock:
            local = list(self._candidates.values())
        by_id = {bundle.bundle_id: bundle for bundle in local}
        for record in self._decision_store().list_policy_bundle_candidates():
            if record.bundle_id in by_id:
                continue
            try:
                by_id[record.bundle_id] = self._load_from_record(record)
            except Exception:  # noqa: BLE001
                continue
        return list(by_id.values())

    def get_candidate(self, bundle_id: str) -> PolicyBundle | None:
        with self._lock:
            if bundle_id in self._candidates:
                return self._candidates[bundle_id]
            active = get_policy_bundle()
            if active.bundle_id == bundle_id:
                return active
            if self._previous and self._previous.bundle_id == bundle_id:
                return self._previous
        record = self._decision_store().get_policy_bundle_record(bundle_id)
        if record is None:
            return None
        try:
            bundle = self._load_from_record(record)
        except Exception:  # noqa: BLE001
            return None
        if bundle.validation_status == "ok":
            with self._lock:
                self._candidates[bundle.bundle_id] = bundle
                self._candidate_sources[bundle.bundle_id] = dict(record.source_json)
        return bundle

    def validate_from_path(
        self,
        root: Path,
        *,
        source: PolicySource | None = None,
    ) -> PolicyBundle:
        bundle = PolicyBundle.load(root)
        if bundle.validation_status != "ok":
            return bundle
        source = source or PolicySource(type="filesystem", path=str(root))
        source_json = _source_to_json(source)
        if source.type in {"", "filesystem"} and not source_json.get("path"):
            source_json["path"] = str(root)
        with self._lock:
            self._candidates[bundle.bundle_id] = bundle
            self._candidate_sources[bundle.bundle_id] = source_json
        self._decision_store().upsert_policy_bundle_candidate(
            bundle_id=bundle.bundle_id,
            content_digest=bundle.content_digest,
            git_revision=bundle.git_revision,
            source_type=str(source_json.get("type") or "filesystem"),
            source_json=source_json,
            validation_status=bundle.validation_status,
            error=bundle.error,
            loaded_at=bundle.loaded_at,
        )
        return bundle

    def validate_from_source(self, source: PolicySource | None = None) -> PolicyBundle:
        source = source or policy_source_from_env()
        root = materialize_policy_root(source, default_root=get_governance_root())
        bundle = self.validate_from_path(root, source=source)
        with self._lock:
            self._active_source = source
        return bundle

    def bootstrap_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ok": self._bootstrap_error is None
                and get_policy_bundle().validation_status == "ok",
                "error": self._bootstrap_error,
                "fallback_active": self._fallback_active,
                "expected_digest": self._expected_digest,
                "observed_digest": self._observed_digest
                or get_policy_bundle().content_digest,
                "source_type": self._active_source.type,
                "failure_mode": get_policy_failure_mode(),
                "policy_active_generation": self._active_generation,
                "policy_observed_generation": self._observed_generation,
            }

    def sync_active_from_store(self, *, force: bool = False) -> PolicyBundle | None:
        """Reload local active bundle when durable generation advances."""
        store = self._decision_store()
        try:
            active_record = store.get_active_policy_bundle()
        except Exception:  # noqa: BLE001
            return None
        if active_record is None:
            return None
        generation = int(active_record.generation or 0)
        with self._lock:
            if (
                not force
                and generation > 0
                and generation == self._observed_generation
                and get_policy_bundle().content_digest == active_record.content_digest
            ):
                self._active_generation = generation
                return get_policy_bundle()
        try:
            loaded = self._load_from_record(active_record)
            if loaded.validation_status != "ok":
                raise RuntimeError(loaded.error or "active policy bundle invalid")
            if loaded.content_digest != active_record.content_digest:
                raise RuntimeError(
                    "active policy digest mismatch after rematerialize: "
                    f"{loaded.content_digest} != {active_record.content_digest}"
                )
            current = get_policy_bundle()
            with self._lock:
                if (
                    current.validation_status == "ok"
                    and current.content_digest != loaded.content_digest
                ):
                    self._previous = current
                self._set_active(loaded)
                self._observed_generation = generation
                self._active_generation = generation
                self._observed_digest = loaded.content_digest
                self._bootstrap_error = None
                self._fallback_active = False
                if active_record.source_json:
                    self._active_source = _source_from_json(active_record.source_json)
            return loaded
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._bootstrap_error = str(exc)
            return None

    def ensure_bootstrapped(self) -> PolicyBundle:
        """Load active bundle: prefer durable store, else env source seed."""
        with self._lock:
            current = get_policy_bundle()
            source = policy_source_from_env()
            self._active_source = source
            self._expected_digest = source.digest or ""
            try:
                store = self._decision_store()
                durable = store.get_active_policy_bundle()
                if durable is not None:
                    synced = self.sync_active_from_store(force=True)
                    if synced is None:
                        raise RuntimeError(
                            self._bootstrap_error
                            or "failed to sync durable active policy bundle"
                        )
                    return synced

                root = materialize_policy_root(
                    source, default_root=get_governance_root()
                )
                loaded = PolicyBundle.load(root)
                if loaded.validation_status != "ok":
                    raise RuntimeError(loaded.error or "policy bundle invalid")
                source_json = _source_to_json(source)
                if source.type in {"", "filesystem"} and not source_json.get("path"):
                    source_json["path"] = str(root)
                store.upsert_policy_bundle_candidate(
                    bundle_id=loaded.bundle_id,
                    content_digest=loaded.content_digest,
                    git_revision=loaded.git_revision,
                    source_type=str(source_json.get("type") or "filesystem"),
                    source_json=source_json,
                    validation_status=loaded.validation_status,
                    error=loaded.error,
                    loaded_at=loaded.loaded_at,
                )
                activated = store.activate_policy_bundle(
                    loaded.bundle_id,
                    content_digest=loaded.content_digest,
                )
                if current.validation_status == "ok" and current.content_digest != (
                    loaded.content_digest
                ):
                    self._previous = current
                reload_policy_bundle(root=root)
                active = get_policy_bundle()
                self._bootstrap_error = None
                self._fallback_active = False
                self._observed_digest = active.content_digest
                self._observed_generation = int(activated.generation or 0)
                self._active_generation = self._observed_generation
                return active
            except Exception as exc:
                self._bootstrap_error = str(exc)
                mode = get_policy_failure_mode()
                if mode == "last_known_good" and current.validation_status == "ok":
                    self._fallback_active = True
                    self._observed_digest = current.content_digest
                    return current
                self._fallback_active = False
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

        decision_store = store or self._decision_store()
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
        decision_store.save_policy_bundle_impact(
            bundle_id=impact.bundle_id,
            content_digest=impact.content_digest,
            evaluated_decisions=impact.evaluated_decisions,
            unchanged=impact.unchanged,
            allow_to_block=impact.allow_to_block,
            allow_to_approval=impact.allow_to_approval,
            block_to_allow=impact.block_to_allow,
            approval_to_allow=impact.approval_to_allow,
            approval_to_block=impact.approval_to_block,
            other_changes=impact.other_changes,
            sample_changes=impact.sample_changes,
            simulate_limit=limit,
        )
        return impact

    def impact(self, bundle_id: str) -> BundleImpact | None:
        with self._lock:
            cached = self._impacts.get(bundle_id)
        if cached is not None:
            return cached
        record = self._decision_store().get_policy_bundle_impact(bundle_id)
        if record is None:
            return None
        impact = BundleImpact(
            bundle_id=record.bundle_id,
            content_digest=record.content_digest,
            evaluated_decisions=record.evaluated_decisions,
            unchanged=record.unchanged,
            allow_to_block=record.allow_to_block,
            allow_to_approval=record.allow_to_approval,
            block_to_allow=record.block_to_allow,
            approval_to_allow=record.approval_to_allow,
            approval_to_block=record.approval_to_block,
            other_changes=record.other_changes,
            sample_changes=list(record.sample_changes),
        )
        with self._lock:
            self._impacts[bundle_id] = impact
        return impact

    def activate(self, bundle_id: str) -> PolicyBundle:
        with self._lock:
            candidate = self._candidates.get(bundle_id)
            source_json = dict(self._candidate_sources.get(bundle_id) or {})
        if candidate is None or candidate.validation_status != "ok":
            candidate = self.get_candidate(bundle_id)
        if candidate is None or candidate.validation_status != "ok":
            raise KeyError(f"validated policy bundle not found: {bundle_id}")
        if not source_json:
            record = self._decision_store().get_policy_bundle_by_digest(
                bundle_id=candidate.bundle_id,
                content_digest=candidate.content_digest,
            )
            source_json = dict(record.source_json) if record else {}
        if not source_json:
            source_json = {
                "type": "filesystem",
                "path": str(get_governance_root()),
                "reference": "",
                "digest": "",
                "verify_signature": False,
            }
        store = self._decision_store()
        store.upsert_policy_bundle_candidate(
            bundle_id=candidate.bundle_id,
            content_digest=candidate.content_digest,
            git_revision=candidate.git_revision,
            source_type=str(source_json.get("type") or "filesystem"),
            source_json=source_json,
            validation_status=candidate.validation_status,
            error=candidate.error,
            loaded_at=candidate.loaded_at,
        )
        activated = store.activate_policy_bundle(
            candidate.bundle_id,
            content_digest=candidate.content_digest,
        )
        with self._lock:
            current = get_policy_bundle()
            if current.validation_status == "ok":
                self._previous = current
            self._set_active(candidate)
            self._observed_generation = int(activated.generation or 0)
            self._active_generation = self._observed_generation
            self._observed_digest = candidate.content_digest
            self._bootstrap_error = None
            self._fallback_active = False
            return candidate

    def rollback(self) -> PolicyBundle:
        store = self._decision_store()
        with self._lock:
            local_previous = self._previous

        previous_record = store.get_previous_policy_bundle()
        if previous_record is not None:
            activated = store.rollback_policy_bundle()
            synced = self.sync_active_from_store(force=True)
            if synced is not None:
                return synced
            loaded = self._load_from_record(activated)
            if loaded.validation_status != "ok":
                raise RuntimeError(loaded.error or "rollback bundle invalid")
            with self._lock:
                current = get_policy_bundle()
                self._previous = (
                    current if current.validation_status == "ok" else self._previous
                )
                self._set_active(loaded)
                self._observed_generation = int(activated.generation or 0)
                self._active_generation = self._observed_generation
                self._observed_digest = loaded.content_digest
            return loaded

        # Same-digest re-activate leaves no durable previous; use process cache.
        if local_previous is None or local_previous.validation_status != "ok":
            raise RuntimeError("no last-known-good policy bundle to rollback to")
        return self.activate(local_previous.bundle_id)

    def _load_from_record(self, record: PolicyBundleRecord) -> PolicyBundle:
        source = _source_from_json(record.source_json or {})
        root = materialize_policy_root(source, default_root=get_governance_root())
        return PolicyBundle.load(root)

    @staticmethod
    def _set_active(bundle: PolicyBundle) -> None:
        from app import policy_bundle as pb

        with pb._lock:
            pb._bundle = bundle


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
