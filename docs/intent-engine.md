# Intent Engine

Natural-language orchestration: resolve user intent into agent, model, tools, region, and runtime.

## Flow

```text
User message: "Generate quarterly revenue report"
    ↓ POST /intent/resolve
Intent Engine (keyword routes + registries)
    ↓
Orchestration plan:
  agent: finance-copilot
  model: llama3.1:8b
  tools: [jira-read, vault-read]
  region: eu-central
  cluster: eu-prod
  runtime: ollama
    ↓ optional governance evaluate
allow | block | approval_required
```

## API

```bash
curl -sS -X POST http://127.0.0.1:8091/intent/resolve \
  -H 'content-type: application/json' \
  -H 'x-ai-team: finance' \
  -d '{
    "message": "Generate quarterly revenue report",
    "team": "finance",
    "environment": "production",
    "namespace": "ai-prod",
    "run_governance": true
  }'
```

## Route catalog

Intent patterns live in `governance/intent/routes.yaml`:

| Intent | Agent | Region |
| --- | --- | --- |
| `finance_report` | finance-copilot | eu-central |
| `support_ticket` | support-agent | local |
| `platform_ops` | platform-copilot | eu-central |
| `general_assistant` | platform-copilot | local |

## Related

- [Agent Registry](agent-registry.md)
- [Sovereign AI](sovereign-ai.md)
- [MCP Gateway](mcp-gateway.md)
