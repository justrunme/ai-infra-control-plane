# Inventory drift issue template

Use with `GET /drift/actions` (`kind=open_github_issue`) or copy manually.

**Title:** `Inventory drift: <summary from /drift>`

**Body:**

```markdown
## Inventory drift detected

**Summary:** <!-- from /drift.summary -->

**Missing on backend:** <!-- backend:model list -->
**Unexpected on backend:** <!-- backend:model list -->

### Suggested next steps
1. Confirm probe health for Ollama/vLLM.
2. Pull or unload models, or update inventory ConfigMap.
3. Re-check `GET /drift` and `GET /drift/actions` until `in_sync=true`.

### Links
- `/drift`
- `/drift/actions`
- Runbook: `/incidents/runbook?alert=InventoryDriftDetected`
```
