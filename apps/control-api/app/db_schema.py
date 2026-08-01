"""Authoritative decision-store schema and versioned migrations."""

from __future__ import annotations

# Stable advisory-lock key for concurrent DecisionStore startups (Postgres).
SCHEMA_ADVISORY_LOCK_KEY = 0x41494350  # "AICP"

SCHEMA_SQL = """
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
  request_digest TEXT,
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
  resolved_at TEXT,
  used_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_meta (
  event_id TEXT PRIMARY KEY,
  decision_id TEXT,
  event_type TEXT,
  actor TEXT,
  payload_json TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_approvals_status_created
  ON approvals (status, created_at);
CREATE INDEX IF NOT EXISTS idx_approvals_decision_id
  ON approvals (decision_id);
CREATE INDEX IF NOT EXISTS idx_decisions_request_id
  ON decisions (request_id);
CREATE INDEX IF NOT EXISTS idx_decisions_team_created
  ON decisions (team, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_meta_decision_id
  ON audit_meta (decision_id);
"""


def _migration(
    version: str, *, postgres: tuple[str, ...], sqlite: tuple[str, ...]
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    return (version, postgres, sqlite)


_INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS idx_approvals_status_created "
    "ON approvals (status, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_approvals_decision_id "
    "ON approvals (decision_id)",
    "CREATE INDEX IF NOT EXISTS idx_decisions_request_id "
    "ON decisions (request_id)",
    "CREATE INDEX IF NOT EXISTS idx_decisions_team_created "
    "ON decisions (team, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_audit_meta_decision_id "
    "ON audit_meta (decision_id)",
)

# Incremental migrations for databases created before schema_migrations existed.
# Postgres uses IF NOT EXISTS so fresh CREATE TABLE columns do not abort the ledger.
# SQLite (pre-3.35) lacks ADD COLUMN IF NOT EXISTS; duplicate-column is handled in code.
MIGRATIONS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    _migration(
        "002_request_digest",
        postgres=("ALTER TABLE decisions ADD COLUMN IF NOT EXISTS request_digest TEXT",),
        sqlite=("ALTER TABLE decisions ADD COLUMN request_digest TEXT",),
    ),
    _migration(
        "003_approval_used_at",
        postgres=("ALTER TABLE approvals ADD COLUMN IF NOT EXISTS used_at TEXT",),
        sqlite=("ALTER TABLE approvals ADD COLUMN used_at TEXT",),
    ),
    _migration(
        "004_query_indexes",
        postgres=_INDEX_STATEMENTS,
        sqlite=_INDEX_STATEMENTS,
    ),
)

EXPECTED_MIGRATION_VERSIONS: frozenset[str] = frozenset(
    version for version, _postgres, _sqlite in MIGRATIONS
)
