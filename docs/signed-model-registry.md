# Signed model registry

AI supply chain metadata and HMAC attestations for governed model artifacts.

## Registry fields

Each model in `governance/registry/models.yaml` can declare:

| Field | Purpose |
| --- | --- |
| `revision` | Immutable model revision label |
| `artifact_digest` | SHA256 digest of the model artifact (`sha256:…`) |
| `license` | SPDX or commercial license identifier |
| `attestation_signature` | HMAC-SHA256 over canonical metadata |
| `allowed_teams` | Tenant teams permitted to invoke the model |
| `risk_tier` | Existing governance risk classification |

Canonical signing payload:

```text
{model}|{revision}|{artifact_digest}|{risk_tier}|{license}
```

Demo signing key default: `ai-platform-registry-demo` (override with `MODEL_REGISTRY_SIGNING_KEY`).

## Verification modes

| Env | Behavior |
| --- | --- |
| default | Expose attestation metadata; verify signatures when present |
| `MODEL_REGISTRY_VERIFY=true` | Block models with `artifact_digest` but missing/invalid signature |

Runtime clients can pass the artifact they are about to serve via the gateway or control plane API:

```bash
# Through execution plane gateway
curl -sS -X POST http://127.0.0.1:8090/v1/chat/completions \
  -H 'x-ai-model-digest: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' \
  -H 'x-ai-team: platform' \
  -H 'content-type: application/json' \
  -d '{"model":"llama3.1:8b","messages":[{"role":"user","content":"hi"}]}'

# Direct control plane evaluate
curl -sS -X POST http://127.0.0.1:8091/governance/evaluate \
  -H 'x-ai-model-digest: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' \
  -H 'content-type: application/json' \
  -d '{"team":"platform","namespace":"ai-dev","model":"llama3.1:8b","provider":"ollama"}'
```

Digest mismatch → `block` at the registry stage.

## API

```bash
curl -sS http://127.0.0.1:8091/registry/models
curl -sS http://127.0.0.1:8091/registry/models/llama3.1:8b
```

Response includes `attestation_status`: `verified`, `unsigned`, `invalid`, or `not_required`.

## Related

- [Identity and audit trail](identity-audit.md)
- [Runtime enforcement](runtime-enforcement.md)
