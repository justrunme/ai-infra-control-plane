"""Durable store for governance decisions and approvals.

SQLite is the single-node default. PostgreSQL uses ``psycopg_pool.ConnectionPool``.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.db_metrics import observe_db_operation, set_pool_stats
from app.db_schema import (
    EXPECTED_MIGRATION_VERSIONS,
    MIGRATIONS,
    SCHEMA_ADVISORY_LOCK_KEY,
    SCHEMA_SQL,
)
from app.settings import get_settings

_store: DecisionStore | None = None
_lock = threading.Lock()
_sqlite_schema_lock = threading.Lock()


class StoreUnavailableError(RuntimeError):
    """Raised when the authoritative decision store cannot serve requests."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _is_operational_db_error(exc: BaseException) -> bool:
    if isinstance(exc, (sqlite3.Error, OSError, TimeoutError, ConnectionError)):
        return True
    module = type(exc).__module__ or ""
    return module.startswith("psycopg")


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
    tenant_id: str
    environment: str
    model: str
    subject: str
    reasons: list[Any]
    stages: dict[str, Any]
    request: dict[str, Any]
    request_digest: str
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
    used_at: str | None = None


@dataclass(frozen=True)
class ApprovalPage:
    items: list[ApprovalRecord]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


@dataclass(frozen=True)
class RetentionPurgeResult:
    retention_days: int
    cutoff: str
    dry_run: bool
    expired_approvals: int
    deleted_audit_meta: int
    deleted_approvals: int
    deleted_decisions: int


class DecisionStore:
    """Durable decision / approval store (SQLite or pooled Postgres)."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._backend = "sqlite"
        self._pg = False
        self._op_lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._pool: Any = None

        if database_url.startswith(("postgres://", "postgresql://")):
            try:
                from psycopg.rows import dict_row
                from psycopg_pool import ConnectionPool
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "DATABASE_URL is postgres but psycopg/psycopg_pool is not installed"
                ) from exc
            self._backend = "postgres"
            self._pg = True
            self._pool = ConnectionPool(
                conninfo=database_url,
                min_size=1,
                max_size=10,
                timeout=5.0,
                kwargs={"row_factory": dict_row},
                open=True,
            )
            with self._pool.connection() as conn:
                self._apply_schema(conn, postgres=True)
            self.assert_migrations_current()
            self._refresh_pool_stats()
            return

        path = sqlite_path_from_url(database_url)
        _ensure_sqlite_parent(path)
        # Serialize connect+schema so concurrent startups cannot race WAL/DDL.
        with _sqlite_schema_lock:
            self._conn = sqlite3.connect(path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=15000")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._apply_schema(self._conn, postgres=False)
            self.assert_migrations_current()
        set_pool_stats(backend="sqlite", size=1, available=1)

    @classmethod
    def from_env(cls) -> DecisionStore:
        return cls(get_settings().database_url)

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None
        if self._conn is not None:
            with self._op_lock:
                self._conn.close()
            self._conn = None

    def _refresh_pool_stats(self) -> None:
        if self._pool is None:
            set_pool_stats(backend=self._backend, size=1, available=1)
            return
        stats = self._pool.get_stats()
        set_pool_stats(
            backend="postgres",
            size=int(stats.get("pool_size", 0) or 0),
            available=int(stats.get("pool_available", 0) or 0),
        )

    def ping(self) -> bool:
        try:
            with observe_db_operation("ping"):
                with self._session() as conn:
                    cur = self._execute(conn, "SELECT 1")
                    cur.fetchone()
            self._refresh_pool_stats()
            return True
        except Exception:  # noqa: BLE001
            return False

    def pool_stats(self) -> dict[str, int | str]:
        self._refresh_pool_stats()
        from app import db_metrics

        return {
            "backend": db_metrics.DB_BACKEND,
            "size": db_metrics.DB_POOL_SIZE,
            "available": db_metrics.DB_POOL_AVAILABLE,
        }

    @contextmanager
    def _session(self) -> Iterator[Any]:
        if self._pg:
            assert self._pool is not None
            with self._pool.connection() as conn:
                yield conn
            self._refresh_pool_stats()
            return
        assert self._conn is not None
        with self._op_lock:
            yield self._conn

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        """Unit of Work: commit on success, rollback on error."""
        with self._session() as conn:
            try:
                yield conn
                self._commit(conn)
            except Exception:
                try:
                    conn.rollback()
                except Exception:  # noqa: BLE001
                    pass
                raise

    def _apply_schema(self, conn: Any, *, postgres: bool) -> None:
        if postgres:
            statements = [part.strip() for part in SCHEMA_SQL.split(";") if part.strip()]
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
            conn.commit()
            self._run_migrations(conn, postgres=True)
            return
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        self._run_migrations(conn, postgres=False)

    def _run_migrations(self, conn: Any, *, postgres: bool) -> None:
        if postgres:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_lock(%s)", (SCHEMA_ADVISORY_LOCK_KEY,))
            try:
                self._apply_pending_migrations(conn, postgres=True)
                conn.commit()
            finally:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT pg_advisory_unlock(%s)", (SCHEMA_ADVISORY_LOCK_KEY,)
                    )
                conn.commit()
            return
        self._apply_pending_migrations(conn, postgres=False)

    def _apply_pending_migrations(self, conn: Any, *, postgres: bool) -> None:
        now = _isoformat(_utcnow())
        for version, postgres_statements, sqlite_statements in MIGRATIONS:
            if self._migration_applied(conn, version, postgres=postgres):
                continue
            statements = postgres_statements if postgres else sqlite_statements
            for statement in statements:
                self._execute_migration_statement(
                    conn, statement, postgres=postgres
                )
            if postgres:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO schema_migrations (version, applied_at)
                        VALUES (%s, %s)
                        ON CONFLICT (version) DO NOTHING
                        """,
                        (version, now),
                    )
            else:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO schema_migrations (version, applied_at)
                    VALUES (?, ?)
                    """,
                    (version, now),
                )
            conn.commit()
            if not self._migration_applied(conn, version, postgres=postgres):
                raise RuntimeError(f"failed to record schema migration {version}")

    def _execute_migration_statement(
        self, conn: Any, statement: str, *, postgres: bool
    ) -> None:
        if postgres:
            with conn.cursor() as cur:
                cur.execute("SAVEPOINT mig_step")
                try:
                    cur.execute(statement)
                    cur.execute("RELEASE SAVEPOINT mig_step")
                except Exception:
                    cur.execute("ROLLBACK TO SAVEPOINT mig_step")
                    raise
            return
        try:
            conn.execute(statement)
        except sqlite3.OperationalError as exc:
            # Older SQLite without IF NOT EXISTS on ADD COLUMN.
            message = str(exc).lower()
            if "duplicate column" in message or "already exists" in message:
                return
            raise

    def _migration_applied(self, conn: Any, version: str, *, postgres: bool) -> bool:
        query = (
            "SELECT 1 FROM schema_migrations WHERE version = %s"
            if postgres
            else "SELECT 1 FROM schema_migrations WHERE version = ?"
        )
        if postgres:
            with conn.cursor() as cur:
                cur.execute(query, (version,))
                return cur.fetchone() is not None
        cur = conn.execute(query, (version,))
        return cur.fetchone() is not None

    def list_schema_migrations(self) -> set[str]:
        """Return applied migration versions from the ledger."""
        with self._session() as conn:
            if self._pg:
                with conn.cursor() as cur:
                    cur.execute("SELECT version FROM schema_migrations")
                    rows = cur.fetchall()
            else:
                rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
        versions: set[str] = set()
        for row in rows:
            mapping = self._as_mapping(row)
            version = mapping.get("version")
            if version:
                versions.add(str(version))
        return versions

    def assert_migrations_current(self) -> None:
        applied = self.list_schema_migrations()
        missing = EXPECTED_MIGRATION_VERSIONS - applied
        if missing:
            raise RuntimeError(
                "schema_migrations incomplete: missing "
                + ", ".join(sorted(missing))
            )

    def _execute(self, conn: Any, sql: str, params: tuple[Any, ...] = ()) -> Any:
        if self._pg:
            sql = sql.replace("?", "%s")
        return conn.execute(sql, params)

    def _commit(self, conn: Any) -> None:
        conn.commit()

    def _wrap_db(self, _exc: BaseException) -> StoreUnavailableError:
        return StoreUnavailableError("authoritative store unavailable")

    def create_decision(
        self,
        *,
        final_verdict: str,
        request_id: str = "",
        policy_bundle_id: str = "",
        policy_digest: str = "",
        team: str = "",
        tenant_id: str = "",
        environment: str = "",
        model: str = "",
        subject: str = "",
        reasons: list[Any] | None = None,
        stages: dict[str, Any] | None = None,
        request: dict[str, Any] | None = None,
        request_digest: str = "",
        decision_id: str | None = None,
        conn: Any | None = None,
    ) -> str:
        decision_id = decision_id or str(uuid.uuid4())
        created_at = _isoformat(_utcnow())
        effective_tenant = (tenant_id or team or "").strip()
        params = (
            decision_id,
            request_id,
            final_verdict,
            policy_bundle_id,
            policy_digest,
            team,
            effective_tenant,
            environment,
            model,
            subject,
            json.dumps(reasons or []),
            json.dumps(stages or {}),
            json.dumps(request or {}),
            request_digest,
            created_at,
        )
        sql = """
            INSERT INTO decisions (
              decision_id, request_id, final_verdict, policy_bundle_id,
              policy_digest, team, tenant_id, environment, model, subject,
              reasons_json, stages_json, request_json, request_digest,
              created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        try:
            with observe_db_operation("create_decision"):
                if conn is not None:
                    self._execute(conn, sql, params)
                else:
                    with self._session() as session:
                        self._execute(session, sql, params)
                        self._commit(session)
        except Exception as exc:  # noqa: BLE001
            if _is_operational_db_error(exc):
                raise self._wrap_db(exc) from exc
            raise
        return decision_id

    def create_approval(
        self,
        decision_id: str,
        ttl_seconds: int,
        *,
        conn: Any | None = None,
    ) -> str:
        approval_id = str(uuid.uuid4())
        now = _utcnow()
        expires_at = now + timedelta(seconds=max(ttl_seconds, 0))
        params = (
            approval_id,
            decision_id,
            "pending",
            None,
            None,
            _isoformat(now),
            _isoformat(expires_at),
            None,
            None,
        )
        sql = """
            INSERT INTO approvals (
              approval_id, decision_id, status, reviewer, review_comment,
              created_at, expires_at, resolved_at, used_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        try:
            with observe_db_operation("create_approval"):
                if conn is not None:
                    self._execute(conn, sql, params)
                else:
                    with self._session() as session:
                        self._execute(session, sql, params)
                        self._commit(session)
        except Exception as exc:  # noqa: BLE001
            if _is_operational_db_error(exc):
                raise self._wrap_db(exc) from exc
            raise
        return approval_id

    def consume_approval(
        self, approval_id: str, *, conn: Any | None = None
    ) -> bool:
        now = _isoformat(_utcnow())
        sql = """
            UPDATE approvals
            SET status = 'consumed', used_at = ?
            WHERE approval_id = ?
              AND status = 'approved'
              AND (used_at IS NULL OR used_at = '')
            """
        try:
            with observe_db_operation("consume_approval"):
                if conn is not None:
                    cur = self._execute(conn, sql, (now, approval_id))
                    return int(cur.rowcount or 0) == 1
                with self._session() as session:
                    cur = self._execute(session, sql, (now, approval_id))
                    self._commit(session)
                    return int(cur.rowcount or 0) == 1
        except Exception as exc:  # noqa: BLE001
            if _is_operational_db_error(exc):
                raise self._wrap_db(exc) from exc
            raise

    def list_recent_decisions(
        self,
        *,
        limit: int = 1000,
        tenant_id: str | None = None,
    ) -> list[DecisionRecord]:
        limit = max(1, min(limit, 5000))
        try:
            with observe_db_operation("list_recent_decisions"):
                with self._session() as conn:
                    if tenant_id is None:
                        cur = self._execute(
                            conn,
                            """
                            SELECT * FROM decisions
                            ORDER BY created_at DESC
                            LIMIT ?
                            """,
                            (limit,),
                        )
                    else:
                        cur = self._execute(
                            conn,
                            """
                            SELECT * FROM decisions
                            WHERE tenant_id = ?
                            ORDER BY created_at DESC
                            LIMIT ?
                            """,
                            (tenant_id, limit),
                        )
                    rows = cur.fetchall()
        except Exception as exc:  # noqa: BLE001
            if _is_operational_db_error(exc):
                raise self._wrap_db(exc) from exc
            raise
        return [self._decision_from_row(row) for row in rows]

    def get_decision(
        self,
        decision_id: str,
        *,
        tenant_id: str | None = None,
    ) -> DecisionRecord | None:
        try:
            with observe_db_operation("get_decision"):
                with self._session() as conn:
                    cur = self._execute(
                        conn,
                        "SELECT * FROM decisions WHERE decision_id = ?",
                        (decision_id,),
                    )
                    row = cur.fetchone()
        except Exception as exc:  # noqa: BLE001
            if _is_operational_db_error(exc):
                raise self._wrap_db(exc) from exc
            raise
        if row is None:
            return None
        record = self._decision_from_row(row)
        if tenant_id is not None and record.tenant_id != tenant_id:
            return None
        return record

    def get_approval(
        self,
        approval_id: str,
        *,
        tenant_id: str | None = None,
    ) -> ApprovalRecord | None:
        try:
            with observe_db_operation("get_approval"):
                with self._session() as conn:
                    self._expire_if_needed(conn, approval_id)
                    cur = self._execute(
                        conn,
                        "SELECT * FROM approvals WHERE approval_id = ?",
                        (approval_id,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        return None
                    approval = self._approval_from_row(row)
                    if tenant_id is None:
                        return approval
                    dec_cur = self._execute(
                        conn,
                        """
                        SELECT tenant_id, team FROM decisions
                        WHERE decision_id = ?
                        """,
                        (approval.decision_id,),
                    )
                    dec_row = dec_cur.fetchone()
                    if dec_row is None:
                        return None
                    mapping = self._as_mapping(dec_row)
                    owner_tenant = mapping.get("tenant_id") or mapping.get("team") or ""
                    if owner_tenant != tenant_id:
                        return None
                    return approval
        except Exception as exc:  # noqa: BLE001
            if _is_operational_db_error(exc):
                raise self._wrap_db(exc) from exc
            raise

    def list_approvals(
        self,
        status: str = "pending",
        *,
        limit: int = 100,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> ApprovalPage:
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        try:
            with observe_db_operation("list_approvals"):
                with self._session() as conn:
                    self._expire_stale(conn)
                    if tenant_id is None:
                        count_sql = (
                            "SELECT COUNT(*) AS total FROM approvals WHERE status = ?"
                        )
                        count_params: tuple[Any, ...] = (status,)
                        list_sql = """
                            SELECT * FROM approvals
                            WHERE status = ?
                            ORDER BY created_at ASC
                            LIMIT ? OFFSET ?
                            """
                        list_params: tuple[Any, ...] = (status, limit, offset)
                    else:
                        count_sql = """
                            SELECT COUNT(*) AS total
                            FROM approvals a
                            JOIN decisions d ON d.decision_id = a.decision_id
                            WHERE a.status = ? AND d.tenant_id = ?
                            """
                        count_params = (status, tenant_id)
                        list_sql = """
                            SELECT a.*
                            FROM approvals a
                            JOIN decisions d ON d.decision_id = a.decision_id
                            WHERE a.status = ? AND d.tenant_id = ?
                            ORDER BY a.created_at ASC
                            LIMIT ? OFFSET ?
                            """
                        list_params = (status, tenant_id, limit, offset)
                    count_cur = self._execute(conn, count_sql, count_params)
                    total = int(
                        self._as_mapping(count_cur.fetchone()).get("total") or 0
                    )
                    cur = self._execute(conn, list_sql, list_params)
                    rows = cur.fetchall()
        except Exception as exc:  # noqa: BLE001
            if _is_operational_db_error(exc):
                raise self._wrap_db(exc) from exc
            raise
        return ApprovalPage(
            items=[self._approval_from_row(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def count_approvals(self, status: str = "pending") -> int:
        try:
            with observe_db_operation("count_approvals"):
                with self._session() as conn:
                    self._expire_stale(conn)
                    cur = self._execute(
                        conn,
                        "SELECT COUNT(*) AS total FROM approvals WHERE status = ?",
                        (status,),
                    )
                    return int(self._as_mapping(cur.fetchone()).get("total") or 0)
        except Exception as exc:  # noqa: BLE001
            if _is_operational_db_error(exc):
                raise self._wrap_db(exc) from exc
            raise

    def resolve_approval(
        self,
        approval_id: str,
        status: str,
        reviewer: str,
        comment: str = "",
    ) -> ApprovalRecord:
        if status not in {"approved", "rejected"}:
            raise ValueError("status must be 'approved' or 'rejected'")

        try:
            with observe_db_operation("resolve_approval"):
                with self._session() as conn:
                    self._expire_if_needed(conn, approval_id)
                    cur = self._execute(
                        conn,
                        "SELECT * FROM approvals WHERE approval_id = ?",
                        (approval_id,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise KeyError(f"approval not found: {approval_id}")
                    approval = self._approval_from_row(row)
                    if approval.status == "expired":
                        raise ValueError("approval expired")
                    if approval.status != "pending":
                        raise ValueError(
                            f"approval is not pending (status={approval.status})"
                        )
                    resolved_at = _isoformat(_utcnow())
                    self._execute(
                        conn,
                        """
                        UPDATE approvals
                        SET status = ?, reviewer = ?, review_comment = ?, resolved_at = ?
                        WHERE approval_id = ?
                        """,
                        (status, reviewer, comment, resolved_at, approval_id),
                    )
                    self._commit(conn)
                    cur = self._execute(
                        conn,
                        "SELECT * FROM approvals WHERE approval_id = ?",
                        (approval_id,),
                    )
                    updated_row = cur.fetchone()
        except (KeyError, ValueError):
            raise
        except Exception as exc:  # noqa: BLE001
            if _is_operational_db_error(exc):
                raise self._wrap_db(exc) from exc
            raise
        assert updated_row is not None
        return self._approval_from_row(updated_row)

    def expire_stale_approvals(self) -> int:
        try:
            with observe_db_operation("expire_stale_approvals"):
                with self._session() as conn:
                    return self._expire_stale(conn)
        except Exception as exc:  # noqa: BLE001
            if _is_operational_db_error(exc):
                raise self._wrap_db(exc) from exc
            raise

    def purge_retained(
        self,
        *,
        retention_days: int,
        dry_run: bool = True,
        limit: int = 5000,
    ) -> RetentionPurgeResult:
        """Expire stale approvals, then delete rows older than retention_days.

        Deletes decisions (and cascaded approvals/audit_meta) with ``created_at``
        before the cutoff. ``retention_days <= 0`` disables deletion (expire only).
        """
        if limit < 1 or limit > 50_000:
            raise ValueError("limit must be between 1 and 50000")
        cutoff_dt = _utcnow() - timedelta(days=max(retention_days, 0))
        cutoff = _isoformat(cutoff_dt)
        try:
            with observe_db_operation("purge_retained"):
                with self.transaction() as conn:
                    expired = self._expire_stale(conn, commit=False)
                    if retention_days <= 0:
                        return RetentionPurgeResult(
                            retention_days=retention_days,
                            cutoff=cutoff,
                            dry_run=dry_run,
                            expired_approvals=expired,
                            deleted_audit_meta=0,
                            deleted_approvals=0,
                            deleted_decisions=0,
                        )
                    ids_cur = self._execute(
                        conn,
                        """
                        SELECT decision_id FROM decisions
                        WHERE created_at < ?
                        ORDER BY created_at ASC
                        LIMIT ?
                        """,
                        (cutoff, limit),
                    )
                    decision_ids = [
                        str(self._as_mapping(row)["decision_id"])
                        for row in ids_cur.fetchall()
                    ]
                    if not decision_ids:
                        return RetentionPurgeResult(
                            retention_days=retention_days,
                            cutoff=cutoff,
                            dry_run=dry_run,
                            expired_approvals=expired,
                            deleted_audit_meta=0,
                            deleted_approvals=0,
                            deleted_decisions=0,
                        )
                    placeholders = ", ".join("?" for _ in decision_ids)
                    audit_cur = self._execute(
                        conn,
                        f"SELECT COUNT(*) AS total FROM audit_meta "
                        f"WHERE decision_id IN ({placeholders})",
                        tuple(decision_ids),
                    )
                    approval_cur = self._execute(
                        conn,
                        f"SELECT COUNT(*) AS total FROM approvals "
                        f"WHERE decision_id IN ({placeholders})",
                        tuple(decision_ids),
                    )
                    deleted_audit = int(
                        self._as_mapping(audit_cur.fetchone()).get("total") or 0
                    )
                    deleted_approvals = int(
                        self._as_mapping(approval_cur.fetchone()).get("total") or 0
                    )
                    deleted_decisions = len(decision_ids)
                    if not dry_run:
                        id_params = tuple(decision_ids)
                        self._execute(
                            conn,
                            (
                                "DELETE FROM audit_meta "
                                f"WHERE decision_id IN ({placeholders})"
                            ),
                            id_params,
                        )
                        self._execute(
                            conn,
                            (
                                "DELETE FROM approvals "
                                f"WHERE decision_id IN ({placeholders})"
                            ),
                            id_params,
                        )
                        self._execute(
                            conn,
                            (
                                "DELETE FROM decisions "
                                f"WHERE decision_id IN ({placeholders})"
                            ),
                            id_params,
                        )
                    return RetentionPurgeResult(
                        retention_days=retention_days,
                        cutoff=cutoff,
                        dry_run=dry_run,
                        expired_approvals=expired,
                        deleted_audit_meta=deleted_audit,
                        deleted_approvals=deleted_approvals,
                        deleted_decisions=deleted_decisions,
                    )
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001
            if _is_operational_db_error(exc):
                raise self._wrap_db(exc) from exc
            raise

    def append_audit_meta(
        self,
        *,
        decision_id: str,
        event_type: str,
        actor: str = "",
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
        conn: Any | None = None,
    ) -> str:
        event_id = event_id or str(uuid.uuid4())
        params = (
            event_id,
            decision_id,
            event_type,
            actor,
            json.dumps(payload or {}),
            _isoformat(_utcnow()),
        )
        sql = """
            INSERT INTO audit_meta (
              event_id, decision_id, event_type, actor,
              payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """
        try:
            with observe_db_operation("append_audit_meta"):
                if conn is not None:
                    self._execute(conn, sql, params)
                else:
                    with self._session() as session:
                        self._execute(session, sql, params)
                        self._commit(session)
        except Exception as exc:  # noqa: BLE001
            if _is_operational_db_error(exc):
                raise self._wrap_db(exc) from exc
            raise
        return event_id

    def _expire_stale(self, conn: Any, *, commit: bool = True) -> int:
        now = _isoformat(_utcnow())
        cur = self._execute(
            conn,
            """
            UPDATE approvals
            SET status = 'expired', resolved_at = ?
            WHERE status = 'pending' AND expires_at <= ?
            """,
            (now, now),
        )
        if commit:
            self._commit(conn)
        return int(cur.rowcount or 0)

    def _expire_if_needed(self, conn: Any, approval_id: str) -> None:
        cur = self._execute(
            conn,
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
            conn,
            """
            UPDATE approvals
            SET status = 'expired', resolved_at = ?
            WHERE approval_id = ? AND status = 'pending'
            """,
            (now, approval_id),
        )
        self._commit(conn)

    @staticmethod
    def _as_mapping(row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return row
        try:
            return dict(row)
        except (TypeError, ValueError):
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
        team = mapping.get("team") or ""
        tenant_id = mapping.get("tenant_id") or team
        return DecisionRecord(
            decision_id=mapping["decision_id"],
            request_id=mapping.get("request_id") or "",
            final_verdict=mapping.get("final_verdict") or "",
            policy_bundle_id=mapping.get("policy_bundle_id") or "",
            policy_digest=mapping.get("policy_digest") or "",
            team=team,
            tenant_id=tenant_id,
            environment=mapping.get("environment") or "",
            model=mapping.get("model") or "",
            subject=mapping.get("subject") or "",
            reasons=json.loads(mapping.get("reasons_json") or "[]"),
            stages=json.loads(mapping.get("stages_json") or "{}"),
            request=json.loads(mapping.get("request_json") or "{}"),
            request_digest=mapping.get("request_digest") or "",
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
            used_at=mapping.get("used_at"),
        )


def get_decision_store() -> DecisionStore:
    """Return the process-wide decision store singleton."""
    global _store
    if _store is not None:
        return _store
    with _lock:
        if _store is not None:
            return _store
        try:
            _store = DecisionStore.from_env()
        except Exception as exc:  # noqa: BLE001
            if isinstance(exc, StoreUnavailableError):
                raise
            raise StoreUnavailableError(
                "authoritative store unavailable"
            ) from exc
    return _store


def reset_decision_store(store: DecisionStore | None = None) -> None:
    """Replace or clear the singleton (tests)."""
    global _store
    with _lock:
        if _store is not None and store is not _store:
            try:
                _store.close()
            except Exception:  # noqa: BLE001
                pass
        _store = store
