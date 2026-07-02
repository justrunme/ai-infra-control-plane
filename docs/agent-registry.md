# Agent Registry

Catalog of governed agents with model, tool, and policy bindings.

## Registry fields

| Field | Purpose |
| --- | --- |
| `owner` | Owning team |
| `model` | Bound model from Model Registry |
| `policy_pack` | Default policy pack |
| `tools` | Allowed MCP tools |
| `memory_ttl_days` | Memory retention hint |
| `allowed_teams` | Tenant teams permitted to run the agent |
| `forbidden` | Hard deny |

## API

```bash
curl -sS http://127.0.0.1:8091/registry/agents
curl -sS http://127.0.0.1:8091/registry/agents/platform-copilot
```

## Governance binding

When `agent` is set on evaluate or evaluate-tool, the control plane validates team, namespace, model, and tool bindings.

```bash
curl -sS -X POST http://127.0.0.1:8091/governance/evaluate-tool \
  -H 'content-type: application/json' \
  -H 'x-ai-team: platform' \
  -H 'x-ai-agent: platform-copilot' \
  -d '{"agent":"platform-copilot","tool":"jira-read","action":"read","namespace":"ai-dev"}'
```

## Related

- [MCP Gateway](mcp-gateway.md)
- [Tool Registry](tool-registry.md)
