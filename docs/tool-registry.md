# Tool Registry

Catalog of MCP tools with owner, risk, action allowlists, and team bindings.

## Registry fields

| Field | Purpose |
| --- | --- |
| `owner` | Owning team or service |
| `risk_tier` | low / medium / high / critical |
| `mcp_server` | Upstream MCP server identifier |
| `allowed_actions` | Permitted verbs (read, list, write, delete) |
| `forbidden_actions` | Explicitly denied verbs |
| `allowed_teams` | Tenant teams permitted to invoke the tool |
| `forbidden` | Hard deny regardless of other fields |

## API

```bash
curl -sS http://127.0.0.1:8091/registry/tools
curl -sS http://127.0.0.1:8091/registry/tools/jira-read
```

## Governance

```bash
curl -sS -X POST http://127.0.0.1:8091/governance/evaluate-tool \
  -H 'content-type: application/json' \
  -H 'x-ai-team: platform' \
  -d '{"tool":"kubernetes-admin","action":"delete","namespace":"ai-dev"}'
```

## Related

- [MCP Gateway](mcp-gateway.md)
- [Agent Registry](agent-registry.md)
