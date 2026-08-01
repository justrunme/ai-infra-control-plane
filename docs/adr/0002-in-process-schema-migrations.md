# ADR 0002: In-process schema migrations over Alembic

## Status

Accepted (v1.0, reaffirmed v1.4)

## Context

Operators asked whether Alembic should own schema evolution. The control plane
already has a versioned `schema_migrations` ledger with advisory locks and
dialect-aware SQL.

## Decision

Keep **in-process migrations** applied on DecisionStore startup.

Defer Alembic/CLI packaging until there is a multi-service shared database or
offline expand/contract requirement.

## Consequences

- Zero extra operator tool for reference and single-chart installs.
- Migration quality must stay high (ledger tests, concurrent startup tests).
- Large online DDL still requires careful migration authorship.
