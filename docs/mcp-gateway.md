# MCP Gateway

Governed MCP tool access through the execution plane gateway.

## Flow

```text
Agent / Client
    ↓ POST /mcp/tools/{tool}/call
Execution Plane (MCP Gateway)
    ↓ POST /governance/evaluate-tool
Control Plane (Tool Registry)
    ↓ allow | block
MCP backend (or governed stub in demo)
```

## Tool call API

```bash
# Allowed read on Jira
curl -sS -X POST http://127.0.0.1:8090/mcp/tools/jira-read/call \
  -H 'content-type: application/json' \
  -H 'x-ai-team: platform' \
  -d '{"action":"read","arguments":{"issue":"PROJ-1"}}'

# Blocked delete on Kubernetes
curl -sS -X POST http://127.0.0.1:8090/mcp/tools/kubernetes-admin/call \
  -H 'content-type: application/json' \
  -H 'x-ai-team: platform' \
  -d '{"action":"delete","arguments":{"resource":"pod/demo"}}'
```

## Headers

| Header | Purpose |
| --- | --- |
| `x-ai-team` | Tenant team for tool allowlist |
| `x-ai-namespace` | Namespace scope |
| `x-ai-agent` | Optional agent binding (Agent Registry) |
| `Authorization` | OIDC JWT for identity resolution |

## Control plane endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/registry/tools` | Tool catalog |
| `GET` | `/registry/tools/{name}` | Single tool entry |
| `POST` | `/governance/evaluate-tool` | Narrow tool governance verdict |

## Related

- [Tool Registry](tool-registry.md)
- [Agent Registry](agent-registry.md)
- [Runtime enforcement mode](https://github.com/justrunme/ai-runtime-platform/blob/main/docs/runtime-enforcement-mode.md)
