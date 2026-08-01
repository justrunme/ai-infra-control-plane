# Threat Model (v1.4)

Scope: Control Plane governance path (evaluate → durable decision/approval →
runtime enforcement consumers). Execution-plane inference is out of scope except
where inventory probes touch it.

## Assets

| Asset | Why it matters |
| --- | --- |
| Policy bundle digest | Prevents silent policy swap |
| Decision / approval records | Authoritative allow/deny evidence |
| Request digests | Bind approvals to exact intent (incl. cost/tokens) |
| Approver identity | Prevents unauthorized policy exceptions |
| Tenant-scoped records | Prevents cross-team data leakage |
| Inventory desired state | Prevents shadow models |

## Trust boundaries

```text
Client / Gateway
  --OIDC Bearer / attribution headers-->
Control API
  --policy bundle files-->
Governance engine
  --SQL-->
Decision store (SQLite|Postgres)
  --probes-->
Model backends (Ollama/vLLM)
```

## Key threats and mitigations

| Threat | Mitigation |
| --- | --- |
| Approval replay / request swap | Request digest binding + one-time consume |
| Cost/token inflation after approve | Cost/token fields in digest |
| Cross-tenant decision fetch | `TENANT_ISOLATION` + 404 on mismatch |
| Unauthenticated approve/reject | OIDC JWT verify + approver groups (prod profile) |
| SQLite multi-replica split brain | Helm validation refuses SQLite + replicas>1 |
| Store outage fail-open | Fail-closed 503 on store errors |
| Inventory drift unnoticed | Metrics + PrometheusRule + `/drift/actions` |
| Supply-chain image swap | Cosign-signed images and OCI Helm charts |

## Residual risks

- Demo mode without JWT verify trusts body/header identity (intentional).
- Drift actions do not auto-remediate; operators can ignore suggestions.
- Tenant isolation depends on correct gateway header/claim propagation.

## Related

- [ADR 0001 Tenant isolation](adr/0001-tenant-isolation.md)
- [Maturity boundary](maturity-boundary.md)
- [Failure injection](failure-injection.md)
