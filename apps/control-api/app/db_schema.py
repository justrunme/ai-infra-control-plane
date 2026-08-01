"""Authoritative decision-store schema and versioned migrations."""

from __future__ import annotations

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
"""

# Incremental migrations for databases created before schema_migrations existed.
MIGRATIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "002_request_digest",
        ("ALTER TABLE decisions ADD COLUMN request_digest TEXT",),
    ),
    (
        "003_approval_used_at",
        ("ALTER TABLE approvals ADD COLUMN used_at TEXT",),
    ),
)
