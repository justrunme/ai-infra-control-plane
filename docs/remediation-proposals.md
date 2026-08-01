# Remediation proposals

Closed-loop path for inventory drift:

```text
Detect → Propose → Evaluate policy → Approve → PR draft → Applied (GitOps) → Verify
```

The control plane **does not** pull models or rewrite production inventory. It
records proposals, evaluates policy, drafts GitOps PR text, and verifies runtime
drift after apply.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/remediation/proposals` | Create from live (or injected) drift |
| GET | `/remediation/proposals` | List (optional `status`, pagination) |
| GET | `/remediation/proposals/{id}` | Get one |
| POST | `/remediation/proposals/{id}/evaluate-policy` | Run governance evaluate |
| POST | `/remediation/proposals/{id}/approve` | Approve (`approval_required`) |
| POST | `/remediation/proposals/{id}/reject` | Reject |
| POST | `/remediation/proposals/{id}/prepare-pr` | Persist PR draft (+ optional URL) |
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
5. `POST .../prepare-pr` → open PR externally from `pr_title` / `pr_body`
6. Merge / Argo sync
7. `POST .../mark-applied`
8. `POST .../verify` until `verified`

## Related

- [ADR 0004](adr/0004-remediation-proposal-closed-loop.md)
- [ADR 0003](adr/0003-suggested-drift-actions.md)
- [Policy bundles GitOps](policy-bundles-gitops.md)
