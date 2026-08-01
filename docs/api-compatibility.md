# API Compatibility Policy

## Contract

The frozen OpenAPI document is `apps/control-api/openapi.json`.

CI enforces two checks:

1. **Freeze sync** — `scripts/check_openapi_freeze.py`  
   `live OpenAPI == committed openapi.json`
2. **Backward compatibility** — `scripts/check_openapi_breaking.sh`  
   `oasdiff breaking` against `OPENAPI_BASELINE_TAG` (default `v1.0.0`)

To intentionally change the contract:

```sh
PYTHONPATH=apps/control-api python scripts/export_openapi.py
```

Commit the updated `openapi.json` in the same PR and document the change here.
Breaking changes require a **major** release; set `ALLOW_OPENAPI_BREAKING=1` only
for that controlled major bump, then move the baseline tag policy forward.

## Stability rules (v2.0+)

v2.0 is a stability major for CRDs and Supported surface area. REST OpenAPI
remains checked against baseline tag `v1.0.0` until an intentional breaking
bump moves `OPENAPI_BASELINE_TAG` forward.

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
