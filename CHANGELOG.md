# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.5.0] - 2026-10-10

### Added
- Multi-architecture container images (linux/amd64, linux/arm64)
- Build provenance attestation via GitHub Actions
- SBOM generation and attachment to releases
- Cosign signature verification in CI pipeline
- `:main` tag for container images on pushes to main branch
- Dependabot configuration with grouped updates for Python, GitHub Actions, Docker, and Terraform
- SECURITY.md security policy
- This changelog

### Changed
- Python test matrix extended to include 3.12 and 3.13
- Argo CD installed in kind e2e tests with real sync status verification
- PyJWT and other Python dependency bumps
- Release workflow attestation permissions (attestations, id-token, packages, contents)

## [2.4.0] - 2026-08-01

### Added
- Capability-bound execution digests

## [2.3.0] - 2026-08-01

### Added
- Runtime verification contract

## [2.2.0] - 2026-08-01

### Added
- GitOpsProvider with optional GitHub draft PRs

## [2.1.0] - 2026-08-01

### Added
- Durable HA PolicyBundle lifecycle

## [2.0.1] - 2026-08-01

### Fixed
- v2.0.1 security and correctness patch
- RBAC enforcement
- Policy fail-closed behavior
- OCI tooling improvements

## [2.0.0] - 2026-08-01

### Added
- Stabilized CRDs and Supported surface for v2.0.0
- Formal API stability guarantees

### Changed
- Breaking changes for v2.0 upgrade (see docs/upgrade-v1-to-v2.0.md)

## [1.8.0] - 2026-08-01

### Added
- Durable agent/tool capability contracts

## [1.7.0] - 2026-08-01

### Added
- RBAC roles and permissions
- JWT-only tenant mode
- Quota failure policy (onUnavailable)

## [1.6.0] - 2026-08-01

### Added
- RemediationProposal closed-loop (detect → approve → PR → verify)

## [1.5.0] - 2026-08-01

### Added
- Policy bundle GitOps lifecycle
- Signed OCI PolicyBundle with simulate/activate/rollback

## [1.4.0] - 2026-08-01

### Added
- Enterprise sleep pack
- Tenant isolation capabilities
- PrometheusRule SLO alerts
- Drift action recommendations
- Architecture Decision Records (ADRs)

## [1.3.0] - 2026-08-01

### Added
- Retention purge functionality
- Decision foreign keys
- Signed OCI Helm chart distribution

## [1.2.0] - 2026-08-01

### Added
- OpenAPI breaking-change CI check
- OCI Helm chart packaging and distribution

## [1.1.0] - 2026-08-01

### Added
- Transactional Unit of Work pattern
- Database indexes for performance
- Pagination metadata

## [1.0.1] - 2026-08-01

### Fixed
- Hardened schema migration ledger for Postgres
- Concurrent schema apply correctness

## [1.0.0] - 2026-08-01

### Added
- Stable control-plane contract v1.0
- Connection pooling
- Schema migrations
- Database metrics
- Multi-replica Postgres e2e tests
- Frozen OpenAPI specification
- Unified error handling
- Pagination support
- Compatibility CI

### Changed
- First stable release with API guarantees

## [0.5.0] - 2026-08-01

### Added
- Trust boundary definition
- HA production profile with Postgres
- Readiness checks
- JWKS fail-closed enforcement

## [0.4.0] - 2026-08-01

### Added
- Governance SLO proof
- Failure-injection matrix
- SLO benchmark and dashboard

## [0.3.0] - 2026-08-01

### Added
- Router split from monolith
- Postgres profile support
- kind e2e tests
- Production-ready configuration

## [0.2.0] - 2026-08-01

### Added
- Durable governance foundation
- PolicyBundle versioning
- Durable decisions and approvals
- Probe caching

## [0.1.0] - 2026-07-31

### Added
- Initial enterprise demo
- Agentic governance baseline
- Basic control API
- Model inventory management
- Ollama and vLLM backend probes

[Unreleased]: https://github.com/justrunme/ai-infra-control-plane/compare/v2.5.0...HEAD
[2.5.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v2.4.0...v2.5.0
[2.4.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v2.0.1...v2.1.0
[2.0.1]: https://github.com/justrunme/ai-infra-control-plane/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v1.8.0...v2.0.0
[1.8.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/justrunme/ai-infra-control-plane/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v0.5.0...v1.0.0
[0.5.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/justrunme/ai-infra-control-plane/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/justrunme/ai-infra-control-plane/releases/tag/v0.1.0
