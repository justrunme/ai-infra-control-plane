# Identity and audit trail

Enterprise slice #1: workload identity beyond tenant headers and an immutable governance audit log.

## Workload identity

The control plane resolves identity on every `POST /governance/evaluate` call.

Priority:

1. **OIDC JWT** (`Authorization: Bearer …`) — `sub`, `groups`, `team`, `preferred_username`
2. **Attribution headers** — `x-ai-subject`, `x-ai-team`, `x-ai-groups`, …
3. **JSON body** — playground and direct API clients
4. **Defaults** — `platform` / `anonymous`

JWT handling supports two modes:

| Mode | Env | Behavior |
| --- | --- | --- |
| Prototype (default) | `OIDC_JWT_VERIFY` unset / `false` | Unsigned payload decode for demos |
| Production | `OIDC_JWT_VERIFY=true` | RS256/ES* signature verify via JWKS |

### JWKS verification (Keycloak, Entra ID)

```yaml
env:
  - name: OIDC_JWT_VERIFY
    value: "true"
  - name: OIDC_JWKS_URL
    value: https://keycloak.example.com/realms/ai-platform/protocol/openid-connect/certs
  - name: OIDC_JWT_AUDIENCE
    value: ai-control-plane
  - name: OIDC_JWT_ISSUER
    value: https://keycloak.example.com/realms/ai-platform
```

Keycloak JWKS URL pattern: `{realm-url}/protocol/openid-connect/certs`.

Invalid or tampered tokens are rejected; identity falls back to headers/body defaults.

### Header reference

| Header | Purpose |
| --- | --- |
| `x-ai-subject` | Stable user or service principal ID |
| `x-ai-groups` | Comma-separated groups; first known team wins |
| `x-ai-team` | Tenant / team override |
| `x-request-id` | Correlates gateway request with audit events |

### Example: JWT team from groups

```bash
# Payload: {"sub":"user-42","groups":["finance"],"preferred_username":"bob"}
curl -sS -X POST http://127.0.0.1:8091/governance/evaluate \
  -H "Authorization: Bearer ${DEMO_JWT}" \
  -H 'content-type: application/json' \
  -d '{"model":"llama3.1:8b","provider":"ollama","sensitive_data":true,"requests_last_minute":30}'
```

## Audit trail

Every governance evaluation appends an `AuditEvent`:

| Field | Meaning |
| --- | --- |
| `subject` | Who initiated the request |
| `team` | Tenant used for quota / chargeback |
| `final_verdict` | `allow`, `block`, `approval_required` |
| `blocking_stage` | `quota`, `registry`, `cost`, `approval`, `risk` |
| `reasons` | Human-readable policy outcome |
| `identity_source` | `jwt`, `headers`, `body`, `default` |
| `request_id` | Correlation ID from `x-request-id` |

### Query API

```bash
curl -sS 'http://127.0.0.1:8091/audit/events?team=finance&verdict=block&limit=10'
```

Events are stored in an in-memory ring buffer (`AUDIT_MAX_EVENTS`, default `1000`). For durable retention, enable JSONL and/or Loki — see [Persistent audit trail](persistent-audit.md).

### Metrics

`ai_control_governance_decisions_total{verdict,team,environment}` complements runtime `gateway_governance_decisions_total`.

## Related

- [Workload identity and quotas](workload-identity-quotas.md)
- [Runtime enforcement](runtime-enforcement.md)
