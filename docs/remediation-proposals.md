# Remediation proposals

Closed-loop path for inventory drift:

```text
Detect → Propose → Evaluate policy → Approve → PR draft → Applied (GitOps) → Verify
```

The control plane **does not** pull models or rewrite production inventory. It
records proposals, evaluates policy, opens an optional **draft** GitOps PR, and
verifies runtime drift after apply.

## GitOps provider (v2.2+)

| Mode | When | Behavior |
| --- | --- | --- |
| `noop` (default) | No token/repo, or `GITOPS_PROVIDER=noop` | Persist `pr_title` / `pr_body` only |
| `github` | `GITHUB_TOKEN` + `GITHUB_REPOSITORY`, or `GITOPS_PROVIDER=github` | Create branch + remediation note + **draft** PR; store `pr_url` |

If `prepare-pr` includes `pr_url`, the adapter is skipped. Failures leave the
proposal in `approved` (no half-applied `pr_created`).

## API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/remediation/proposals` | Create from live (or injected) drift |
| GET | `/remediation/proposals` | List (optional `status`, pagination) |
| GET | `/remediation/proposals/{id}` | Get one |
| POST | `/remediation/proposals/{id}/evaluate-policy` | Run governance evaluate |
| POST | `/remediation/proposals/{id}/approve` | Approve (`approval_required`) |
| POST | `/remediation/proposals/{id}/reject` | Reject |
| POST | `/remediation/proposals/{id}/prepare-pr` | Persist PR draft; open GitHub draft PR when configured |
| POST | `/remediation/proposals/{id}/mark-applied` | Signal GitOps applied |
| POST | `/remediation/proposals/{id}/verify` | Re-check `GET /drift` semantics |

Create body (optional):

```json
{
  "action_kind": "pull_model",
  "environment": "production",
  "tenant_id": "platform"
}
```

When policy returns `allow`, the proposal auto-transitions to `approved`.
When `approval_required`, resolve via `/approve` or `/reject` (and the linked
`/approvals/{approval_id}` record).

## Operator flow

1. Confirm drift: `GET /drift` / `GET /drift/actions`
2. `POST /remediation/proposals`
3. `POST .../evaluate-policy`
4. Approve if needed
5. `POST .../prepare-pr` → draft PR via GitOps adapter (or use returned title/body)
6. Merge / Argo sync
7. `POST .../mark-applied`
8. `POST .../verify` until `verified`

## Related

- [ADR 0004](adr/0004-remediation-proposal-closed-loop.md)
- [ADR 0003](adr/0003-suggested-drift-actions.md)
- [Policy bundles GitOps](policy-bundles-gitops.md)
