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
  tenant_id TEXT,
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
  decision_id TEXT REFERENCES decisions(decision_id) ON DELETE CASCADE,
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
  decision_id TEXT REFERENCES decisions(decision_id) ON DELETE CASCADE,
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
CREATE INDEX IF NOT EXISTS idx_decisions_tenant_created
  ON decisions (tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_meta_decision_id
  ON audit_meta (decision_id);
CREATE INDEX IF NOT EXISTS idx_audit_meta_created_at
  ON audit_meta (created_at);
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
    "CREATE INDEX IF NOT EXISTS idx_decisions_tenant_created "
    "ON decisions (tenant_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_audit_meta_decision_id "
    "ON audit_meta (decision_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_meta_created_at "
    "ON audit_meta (created_at)",
)

_POSTGRES_FK_STATEMENTS = (
    """
    DO $$ BEGIN
      ALTER TABLE approvals
        ADD CONSTRAINT approvals_decision_id_fkey
        FOREIGN KEY (decision_id) REFERENCES decisions(decision_id)
        ON DELETE CASCADE;
    EXCEPTION
      WHEN duplicate_object THEN NULL;
    END $$
    """,
    """
    DO $$ BEGIN
      ALTER TABLE audit_meta
        ADD CONSTRAINT audit_meta_decision_id_fkey
        FOREIGN KEY (decision_id) REFERENCES decisions(decision_id)
        ON DELETE CASCADE;
    EXCEPTION
      WHEN duplicate_object THEN NULL;
    END $$
    """,
)

# Incremental migrations for databases created before schema_migrations existed.
# Postgres uses IF NOT EXISTS so fresh CREATE TABLE columns do not abort the ledger.
# SQLite (pre-3.35) lacks ADD COLUMN IF NOT EXISTS; duplicate-column is handled in code.
# SQLite cannot ADD FK to existing tables without rebuild; fresh SCHEMA_SQL has FKs.
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
    _migration(
        "005_decision_foreign_keys",
        postgres=_POSTGRES_FK_STATEMENTS,
        sqlite=(),
    ),
    _migration(
        "006_decision_tenant_id",
        postgres=(
            "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS tenant_id TEXT",
            "UPDATE decisions SET tenant_id = team "
            "WHERE tenant_id IS NULL OR tenant_id = ''",
            "CREATE INDEX IF NOT EXISTS idx_decisions_tenant_created "
            "ON decisions (tenant_id, created_at)",
        ),
        sqlite=(
            "ALTER TABLE decisions ADD COLUMN tenant_id TEXT",
            "UPDATE decisions SET tenant_id = team "
            "WHERE tenant_id IS NULL OR tenant_id = ''",
            "CREATE INDEX IF NOT EXISTS idx_decisions_tenant_created "
            "ON decisions (tenant_id, created_at)",
        ),
    ),
)

EXPECTED_MIGRATION_VERSIONS: frozenset[str] = frozenset(
    version for version, _postgres, _sqlite in MIGRATIONS
)
