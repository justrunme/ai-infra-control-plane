# ADR 0006: Durable agent/tool capability contracts

## Status

Accepted (v1.8)

## Context

Agent and MCP tool registries lived only as YAML on disk. Runtime and evaluate
paths needed a stable, auditable capability contract with digests — without the
control plane executing MCP.

## Decision

Store content-addressed `capability_contracts` (kind=agent|tool) with
draft/active/retired lifecycle. Sync from filesystem YAML; activate retires the
previous active contract for the same name/tenant. Expose registry APIs and an
`AICapabilityContract` CRD for GitOps desired state.

## Consequences

- Runtime can pin to `content_digest` from the control plane.
- YAML catalogs remain for bootstrap and demos.
- MCP execution stays in the runtime plane.
