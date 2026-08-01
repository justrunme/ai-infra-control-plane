# Capability contracts

Durable **agent** and **tool** capability snapshots in the control-plane store.

The control plane is the registry of record. The AI Runtime Platform executes MCP
calls; it should pin against an active contract digest rather than ad-hoc YAML.

## Lifecycle

`draft` → `active` → `retired`

- Sync from filesystem YAML: `POST /registry/capabilities/sync`
- Activate / retire (requires `platform-admin` when JWT verify is on)
- List active overlays: `GET /registry/capabilities/active/{agent|tool}`

Content is content-addressed (`sha256:…`). Re-syncing the same payload is
idempotent.

## API

| Method | Path |
| --- | --- |
| POST | `/registry/capabilities/sync` |
| GET | `/registry/capabilities` |
| GET | `/registry/capabilities/active/{kind}` |
| GET | `/registry/capabilities/{contract_id}` |
| POST | `/registry/capabilities/{contract_id}/activate` |
| POST | `/registry/capabilities/{contract_id}/retire` |

Legacy YAML catalog endpoints (`/registry/agents`, `/registry/tools`) remain for
compatibility.

## GitOps CRD

`AICapabilityContract` (`infra/crd/ai.justrunme.dev_aicapabilitycontracts.yaml`)
declares desired kind/name/digest for GitOps controllers to sync into the API.

## Related

- [Tool registry](tool-registry.md)
- [Agent registry](agent-registry.md)
- [ADR 0006](adr/0006-durable-capability-contracts.md)
