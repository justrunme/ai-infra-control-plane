"""SQLite-backed durable store for governance decisions and approvals.

Postgres URLs (``postgres://`` / ``postgresql://``) are accepted when ``psycopg``
is importable; otherwise only SQLite is supported.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.settings import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
  decision_id TEXT PRIMARY KEY,
  request_id TEXT,
  final_verdict TEXT,
  policy_bundle_id TEXT,
  policy_digest TEXT,
  team TEXT,
  environment TEXT,
  model TEXT,
  subject TEXT,
  reasons_json TEXT,
  stages_json TEXT,
  request_json TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS approvals (
  approval_id TEXT PRIMARY KEY,
  decision_id TEXT,
  status TEXT,
  reviewer TEXT,
  review_comment TEXT,
  created_at TEXT,
  expires_at TEXT,
  resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_meta (
  event_id TEXT PRIMARY KEY,
  decision_id TEXT,
  event_type TEXT,
  actor TEXT,
  payload_json TEXT,
  created_at TEXT
);
"""

_store: DecisionStore | None = None
_lock = threading.Lock()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _isoformat(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def sqlite_path_from_url(database_url: str) -> str:
    """Map a ``sqlite:///`` URL to a filesystem path or ``:memory:``."""
    if database_url in {"sqlite:///:memory:", "sqlite://"}:
        return ":memory:"
    if database_url.startswith("sqlite:////"):
        return "/" + database_url.removeprefix("sqlite:////")
    if database_url.startswith("sqlite:///"):
        return database_url.removeprefix("sqlite:///")
    raise ValueError(f"unsupported sqlite DATABASE_URL: {database_url}")


def _ensure_sqlite_parent(path: str) -> None:
    if path == ":memory:":
        return
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


@dataclass
class DecisionRecord:
    decision_id: str
    request_id: str
    final_verdict: str
    policy_bundle_id: str
    policy_digest: str
    team: str
    environment: str
    model: str
    subject: str
    reasons: list[Any]
    stages: dict[str, Any]
    request: dict[str, Any]
    created_at: str


@dataclass
class ApprovalRecord:
    approval_id: str
    decision_id: str
    status: str
    reviewer: str | None
    review_comment: str | None
    created_at: str
    expires_at: str
    resolved_at: str | None


class DecisionStore:
    """Durable decision / approval store (SQLite by default)."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._backend = "sqlite"
        self._conn: sqlite3.Connection | Any
        self._pg = False

        if database_url.startswith(("postgres://", "postgresql://")):
            try:
                import psycopg
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise RuntimeError(
                    "DATABASE_URL is postgres but psycopg is not installed; "
                    "use a sqlite:/// URL or install psycopg"
                ) from exc
            self._backend = "postgres"
            self._pg = True
            from psycopg.rows import dict_row

            self._conn = psycopg.connect(database_url, row_factory=dict_row)
            self._init_schema_postgres()
            return

        path = sqlite_path_from_url(database_url)
        _ensure_sqlite_parent(path)
        # check_same_thread=False: FastAPI may touch the store from workers.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema_sqlite()

    @classmethod
    def from_env(cls) -> DecisionStore:
        """Construct a store using ``DATABASE_URL`` from settings."""
        return cls(get_settings().database_url)

    def close(self) -> None:
        self._conn.close()

    def _init_schema_sqlite(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def _init_schema_postgres(self) -> None:  # pragma: no cover - optional path
        # Same logical schema; TEXT maps cleanly for this workload.
        statements = [part.strip() for part in _SCHEMA.split(";") if part.strip()]
        with self._conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
        self._conn.commit()

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        if self._pg:  # pragma: no cover - optional path
            sql = sql.replace("?", "%s")
        cur = self._conn.execute(sql, params)
        return cur

    def create_decision(
        self,
        *,
        final_verdict: str,
        request_id: str = "",
        policy_bundle_id: str = "",
        policy_digest: str = "",
        team: str = "",
        environment: str = "",
        model: str = "",
        subject: str = "",
        reasons: list[Any] | None = None,
        stages: dict[str, Any] | None = None,
        request: dict[str, Any] | None = None,
        decision_id: str | None = None,
    ) -> str:
        """Persist a governance decision and return its id."""
        decision_id = decision_id or str(uuid.uuid4())
        created_at = _isoformat(_utcnow())
        self._execute(
            """
            INSERT INTO decisions (
              decision_id, request_id, final_verdict, policy_bundle_id,
              policy_digest, team, environment, model, subject,
              reasons_json, stages_json, request_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                request_id,
                final_verdict,
                policy_bundle_id,
                policy_digest,
                team,
                environment,
                model,
                subject,
                json.dumps(reasons or []),
                json.dumps(stages or {}),
                json.dumps(request or {}),
                created_at,
            ),
        )
        self._conn.commit()
        return decision_id

    def create_approval(self, decision_id: str, ttl_seconds: int) -> str:
        """Create a pending approval linked to ``decision_id``."""
        approval_id = str(uuid.uuid4())
        now = _utcnow()
        expires_at = now + timedelta(seconds=max(ttl_seconds, 0))
        self._execute(
            """
            INSERT INTO approvals (
              approval_id, decision_id, status, reviewer, review_comment,
              created_at, expires_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                approval_id,
                decision_id,
                "pending",
                None,
                None,
                _isoformat(now),
                _isoformat(expires_at),
                None,
            ),
        )
        self._conn.commit()
        return approval_id

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        cur = self._execute(
            "SELECT * FROM decisions WHERE decision_id = ?",
            (decision_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._decision_from_row(row)

    def get_approval(self, approval_id: str) -> ApprovalRecord | None:
        self._expire_if_needed(approval_id)
        cur = self._execute(
            "SELECT * FROM approvals WHERE approval_id = ?",
            (approval_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._approval_from_row(row)

    def list_approvals(self, status: str = "pending") -> list[ApprovalRecord]:
        self.expire_stale_approvals()
        cur = self._execute(
            "SELECT * FROM approvals WHERE status = ? ORDER BY created_at ASC",
            (status,),
        )
        return [self._approval_from_row(row) for row in cur.fetchall()]

    def resolve_approval(
        self,
        approval_id: str,
        status: str,
        reviewer: str,
        comment: str = "",
    ) -> ApprovalRecord:
        """Resolve a pending approval; expire lazily if past TTL."""
        if status not in {"approved", "rejected"}:
            raise ValueError("status must be 'approved' or 'rejected'")

        approval = self.get_approval(approval_id)
        if approval is None:
            raise KeyError(f"approval not found: {approval_id}")
        if approval.status == "expired":
            raise ValueError("approval expired")
        if approval.status != "pending":
            raise ValueError(f"approval is not pending (status={approval.status})")

        resolved_at = _isoformat(_utcnow())
        self._execute(
            """
            UPDATE approvals
            SET status = ?, reviewer = ?, review_comment = ?, resolved_at = ?
            WHERE approval_id = ?
            """,
            (status, reviewer, comment, resolved_at, approval_id),
        )
        self._conn.commit()
        updated = self.get_approval(approval_id)
        assert updated is not None
        return updated

    def expire_stale_approvals(self) -> int:
        """Mark pending approvals past expires_at as expired. Returns count."""
        now = _isoformat(_utcnow())
        cur = self._execute(
            """
            UPDATE approvals
            SET status = 'expired', resolved_at = ?
            WHERE status = 'pending' AND expires_at <= ?
            """,
            (now, now),
        )
        self._conn.commit()
        return int(cur.rowcount or 0)

    def append_audit_meta(
        self,
        *,
        decision_id: str,
        event_type: str,
        actor: str = "",
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> str:
        """Optional helper for audit_meta rows."""
        event_id = event_id or str(uuid.uuid4())
        self._execute(
            """
            INSERT INTO audit_meta (
              event_id, decision_id, event_type, actor, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                decision_id,
                event_type,
                actor,
                json.dumps(payload or {}),
                _isoformat(_utcnow()),
            ),
        )
        self._conn.commit()
        return event_id

    def _expire_if_needed(self, approval_id: str) -> None:
        cur = self._execute(
            "SELECT status, expires_at FROM approvals WHERE approval_id = ?",
            (approval_id,),
        )
        row = cur.fetchone()
        if row is None:
            return
        mapping = self._as_mapping(row)
        status = mapping.get("status")
        expires_at = mapping.get("expires_at")
        if status != "pending" or not expires_at:
            return
        if _parse_iso(str(expires_at)) > _utcnow():
            return
        now = _isoformat(_utcnow())
        self._execute(
            """
            UPDATE approvals
            SET status = 'expired', resolved_at = ?
            WHERE approval_id = ? AND status = 'pending'
            """,
            (now, approval_id),
        )
        self._conn.commit()

    @staticmethod
    def _as_mapping(row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return row
        try:
            return dict(row)
        except (TypeError, ValueError):
            # Fallback for plain tuples (should not happen with dict_row/sqlite3.Row).
            keys = (
                "approval_id",
                "decision_id",
                "status",
                "reviewer",
                "review_comment",
                "created_at",
                "expires_at",
                "resolved_at",
            )
            return {keys[i]: row[i] for i in range(min(len(keys), len(row)))}

    @classmethod
    def _decision_from_row(cls, row: Any) -> DecisionRecord:
        mapping = cls._as_mapping(row)
        return DecisionRecord(
            decision_id=mapping["decision_id"],
            request_id=mapping.get("request_id") or "",
            final_verdict=mapping.get("final_verdict") or "",
            policy_bundle_id=mapping.get("policy_bundle_id") or "",
            policy_digest=mapping.get("policy_digest") or "",
            team=mapping.get("team") or "",
            environment=mapping.get("environment") or "",
            model=mapping.get("model") or "",
            subject=mapping.get("subject") or "",
            reasons=json.loads(mapping.get("reasons_json") or "[]"),
            stages=json.loads(mapping.get("stages_json") or "{}"),
            request=json.loads(mapping.get("request_json") or "{}"),
            created_at=mapping.get("created_at") or "",
        )

    @classmethod
    def _approval_from_row(cls, row: Any) -> ApprovalRecord:
        mapping = cls._as_mapping(row)
        return ApprovalRecord(
            approval_id=mapping["approval_id"],
            decision_id=mapping.get("decision_id") or "",
            status=mapping.get("status") or "",
            reviewer=mapping.get("reviewer"),
            review_comment=mapping.get("review_comment"),
            created_at=mapping.get("created_at") or "",
            expires_at=mapping.get("expires_at") or "",
            resolved_at=mapping.get("resolved_at"),
        )


def get_decision_store() -> DecisionStore:
    """Return the process-wide decision store singleton."""
    global _store
    if _store is not None:
        return _store
    with _lock:
        if _store is None:
            _store = DecisionStore.from_env()
    return _store


def reset_decision_store(store: DecisionStore | None = None) -> None:
    """Replace or clear the singleton (tests)."""
    global _store
    with _lock:
        if _store is not None:
            try:
                _store.close()
            except Exception:  # noqa: BLE001
                pass
        _store = store
