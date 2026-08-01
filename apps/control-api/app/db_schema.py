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

CREATE TABLE IF NOT EXISTS remediation_proposals (
  proposal_id TEXT PRIMARY KEY,
  tenant_id TEXT,
  status TEXT,
  source TEXT,
  remediation_kind TEXT,
  drift_snapshot_json TEXT,
  selected_action_json TEXT,
  decision_id TEXT,
  approval_id TEXT,
  policy_verdict TEXT,
  pr_title TEXT,
  pr_body TEXT,
  pr_url TEXT,
  applied_at TEXT,
  verification_snapshot_json TEXT,
  failure_reason TEXT,
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS capability_contracts (
  contract_id TEXT PRIMARY KEY,
  kind TEXT,
  name TEXT,
  tenant_id TEXT,
  status TEXT,
  version TEXT,
  content_digest TEXT,
  capabilities_json TEXT,
  source TEXT,
  created_at TEXT,
  updated_at TEXT,
  activated_at TEXT
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
CREATE INDEX IF NOT EXISTS idx_remediation_proposals_status_created
  ON remediation_proposals (status, created_at);
CREATE INDEX IF NOT EXISTS idx_remediation_proposals_tenant_created
  ON remediation_proposals (tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_capability_contracts_kind_name_status
  ON capability_contracts (kind, name, status);
CREATE INDEX IF NOT EXISTS idx_capability_contracts_tenant_created
  ON capability_contracts (tenant_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_capability_contracts_digest
  ON capability_contracts (kind, name, tenant_id, content_digest);

CREATE TABLE IF NOT EXISTS policy_bundles (
  record_id TEXT PRIMARY KEY,
  bundle_id TEXT NOT NULL,
  content_digest TEXT NOT NULL,
  git_revision TEXT,
  status TEXT NOT NULL,
  generation INTEGER,
  source_type TEXT,
  source_json TEXT,
  validation_status TEXT,
  error TEXT,
  loaded_at TEXT,
  created_at TEXT,
  updated_at TEXT,
  activated_at TEXT
);

CREATE TABLE IF NOT EXISTS policy_bundle_impacts (
  impact_id TEXT PRIMARY KEY,
  bundle_id TEXT NOT NULL,
  content_digest TEXT NOT NULL,
  evaluated_decisions INTEGER,
  unchanged INTEGER,
  allow_to_block INTEGER,
  allow_to_approval INTEGER,
  block_to_allow INTEGER,
  approval_to_allow INTEGER,
  approval_to_block INTEGER,
  other_changes INTEGER,
  sample_changes_json TEXT,
  simulate_limit INTEGER,
  created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_policy_bundles_status_updated
  ON policy_bundles (status, updated_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_policy_bundles_digest
  ON policy_bundles (bundle_id, content_digest);
CREATE INDEX IF NOT EXISTS idx_policy_bundle_impacts_bundle
  ON policy_bundle_impacts (bundle_id, created_at);
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
    _migration(
        "007_remediation_proposals",
        postgres=(
            """
            CREATE TABLE IF NOT EXISTS remediation_proposals (
              proposal_id TEXT PRIMARY KEY,
              tenant_id TEXT,
              status TEXT,
              source TEXT,
              remediation_kind TEXT,
              drift_snapshot_json TEXT,
              selected_action_json TEXT,
              decision_id TEXT,
              approval_id TEXT,
              policy_verdict TEXT,
              pr_title TEXT,
              pr_body TEXT,
              pr_url TEXT,
              applied_at TEXT,
              verification_snapshot_json TEXT,
              failure_reason TEXT,
              created_at TEXT,
              updated_at TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_remediation_proposals_status_created "
            "ON remediation_proposals (status, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_remediation_proposals_tenant_created "
            "ON remediation_proposals (tenant_id, created_at)",
        ),
        sqlite=(
            """
            CREATE TABLE IF NOT EXISTS remediation_proposals (
              proposal_id TEXT PRIMARY KEY,
              tenant_id TEXT,
              status TEXT,
              source TEXT,
              remediation_kind TEXT,
              drift_snapshot_json TEXT,
              selected_action_json TEXT,
              decision_id TEXT,
              approval_id TEXT,
              policy_verdict TEXT,
              pr_title TEXT,
              pr_body TEXT,
              pr_url TEXT,
              applied_at TEXT,
              verification_snapshot_json TEXT,
              failure_reason TEXT,
              created_at TEXT,
              updated_at TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_remediation_proposals_status_created "
            "ON remediation_proposals (status, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_remediation_proposals_tenant_created "
            "ON remediation_proposals (tenant_id, created_at)",
        ),
    ),
    _migration(
        "008_capability_contracts",
        postgres=(
            """
            CREATE TABLE IF NOT EXISTS capability_contracts (
              contract_id TEXT PRIMARY KEY,
              kind TEXT,
              name TEXT,
              tenant_id TEXT,
              status TEXT,
              version TEXT,
              content_digest TEXT,
              capabilities_json TEXT,
              source TEXT,
              created_at TEXT,
              updated_at TEXT,
              activated_at TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_capability_contracts_kind_name_status "
            "ON capability_contracts (kind, name, status)",
            "CREATE INDEX IF NOT EXISTS idx_capability_contracts_tenant_created "
            "ON capability_contracts (tenant_id, created_at)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_capability_contracts_digest "
            "ON capability_contracts (kind, name, tenant_id, content_digest)",
        ),
        sqlite=(
            """
            CREATE TABLE IF NOT EXISTS capability_contracts (
              contract_id TEXT PRIMARY KEY,
              kind TEXT,
              name TEXT,
              tenant_id TEXT,
              status TEXT,
              version TEXT,
              content_digest TEXT,
              capabilities_json TEXT,
              source TEXT,
              created_at TEXT,
              updated_at TEXT,
              activated_at TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_capability_contracts_kind_name_status "
            "ON capability_contracts (kind, name, status)",
            "CREATE INDEX IF NOT EXISTS idx_capability_contracts_tenant_created "
            "ON capability_contracts (tenant_id, created_at)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_capability_contracts_digest "
            "ON capability_contracts (kind, name, tenant_id, content_digest)",
        ),
    ),
    _migration(
        "009_policy_bundles",
        postgres=(
            """
            CREATE TABLE IF NOT EXISTS policy_bundles (
              record_id TEXT PRIMARY KEY,
              bundle_id TEXT NOT NULL,
              content_digest TEXT NOT NULL,
              git_revision TEXT,
              status TEXT NOT NULL,
              generation INTEGER,
              source_type TEXT,
              source_json TEXT,
              validation_status TEXT,
              error TEXT,
              loaded_at TEXT,
              created_at TEXT,
              updated_at TEXT,
              activated_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS policy_bundle_impacts (
              impact_id TEXT PRIMARY KEY,
              bundle_id TEXT NOT NULL,
              content_digest TEXT NOT NULL,
              evaluated_decisions INTEGER,
              unchanged INTEGER,
              allow_to_block INTEGER,
              allow_to_approval INTEGER,
              block_to_allow INTEGER,
              approval_to_allow INTEGER,
              approval_to_block INTEGER,
              other_changes INTEGER,
              sample_changes_json TEXT,
              simulate_limit INTEGER,
              created_at TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_policy_bundles_status_updated "
            "ON policy_bundles (status, updated_at)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_policy_bundles_digest "
            "ON policy_bundles (bundle_id, content_digest)",
            "CREATE INDEX IF NOT EXISTS idx_policy_bundle_impacts_bundle "
            "ON policy_bundle_impacts (bundle_id, created_at)",
        ),
        sqlite=(
            """
            CREATE TABLE IF NOT EXISTS policy_bundles (
              record_id TEXT PRIMARY KEY,
              bundle_id TEXT NOT NULL,
              content_digest TEXT NOT NULL,
              git_revision TEXT,
              status TEXT NOT NULL,
              generation INTEGER,
              source_type TEXT,
              source_json TEXT,
              validation_status TEXT,
              error TEXT,
              loaded_at TEXT,
              created_at TEXT,
              updated_at TEXT,
              activated_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS policy_bundle_impacts (
              impact_id TEXT PRIMARY KEY,
              bundle_id TEXT NOT NULL,
              content_digest TEXT NOT NULL,
              evaluated_decisions INTEGER,
              unchanged INTEGER,
              allow_to_block INTEGER,
              allow_to_approval INTEGER,
              block_to_allow INTEGER,
              approval_to_allow INTEGER,
              approval_to_block INTEGER,
              other_changes INTEGER,
              sample_changes_json TEXT,
              simulate_limit INTEGER,
              created_at TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_policy_bundles_status_updated "
            "ON policy_bundles (status, updated_at)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_policy_bundles_digest "
            "ON policy_bundles (bundle_id, content_digest)",
            "CREATE INDEX IF NOT EXISTS idx_policy_bundle_impacts_bundle "
            "ON policy_bundle_impacts (bundle_id, created_at)",
        ),
    ),
)

EXPECTED_MIGRATION_VERSIONS: frozenset[str] = frozenset(
    version for version, _postgres, _sqlite in MIGRATIONS
)
