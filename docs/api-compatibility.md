# API Compatibility Policy

## Contract

The frozen OpenAPI document is `apps/control-api/openapi.json`.

CI runs `scripts/check_openapi_freeze.py` and fails on drift. To intentionally
change the contract:

```sh
PYTHONPATH=apps/control-api python scripts/export_openapi.py
```

Commit the updated `openapi.json` in the same PR and document the change here.

## Stability rules (v1.0+)

| Change | Allowed in patch/minor | Requires major |
| --- | --- | --- |
| Add optional response field | Yes | No |
| Add new endpoint | Yes (minor) | No |
| Remove/rename field or path | No | Yes |
| Tighten validation / make field required | No | Yes |
| Change error envelope shape | No | Yes |

## Error envelope

All HTTP errors include:

```json
{
  "error": {
    "code": "decision_store_unavailable",
    "message": "authoritative store unavailable",
    "request_id": "...",
    "retryable": true
  },
  "detail": { "error": "authoritative store unavailable" }
}
```

`detail` remains for backward compatibility with FastAPI clients.
