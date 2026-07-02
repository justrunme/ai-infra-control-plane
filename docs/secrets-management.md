# Secrets management

Enterprise slice #3: keep provider credentials and gateway API keys out of Git, Helm values, and container images.

## Architecture

```text
Vault (source of truth)
  -> External Secrets Operator (sync)
    -> Kubernetes Secret
      -> Pod envFrom
        -> /secrets/status (configured / missing, redacted fingerprint only)
```

The control plane never returns raw secret values. Operators use `/secrets/status` and `ai_control_secret_configured` metrics for drift detection.

## Secret catalog

| Name | Env var | Component | Required |
| --- | --- | --- | --- |
| `gateway_api_keys` | `GATEWAY_API_KEYS` | execution-plane | yes (when auth enabled) |
| `openai_api_key` | `OPENAI_API_KEY` | execution-plane | yes for external OpenAI routes |
| `anthropic_api_key` | `ANTHROPIC_API_KEY` | execution-plane | optional |
| `oidc_client_secret` | `OIDC_CLIENT_SECRET` | shared | optional |
| `audit_signing_key` | `AUDIT_SIGNING_KEY` | control-plane | optional |
| `vault_token` | `VAULT_TOKEN` | shared | optional (prefer K8s auth) |

## Control plane API

```bash
curl -sS http://127.0.0.1:8091/secrets/status | jq
```

Example item:

```json
{
  "name": "openai_api_key",
  "env_var": "OPENAI_API_KEY",
  "status": "configured",
  "fingerprint": "********5678",
  "source": "environment"
}
```

## Kubernetes deployment

1. Install [External Secrets Operator](https://external-secrets.io/).
2. Apply `security/secrets/examples/cluster-secret-store-vault.yaml`.
3. Enable `secrets.externalSecrets` in the Helm chart or apply `security/secrets/examples/external-secret-control-plane.yaml`.
4. Confirm `GET /secrets/status` reports `backend: external-secrets`.

## Local demo

```bash
cp demo/platform/secrets.env.example demo/platform/secrets.env
# edit secrets.env, then:
make platform-demo
```

## Related

- [security/secrets/README.md](../security/secrets/README.md)
- [Identity and audit](identity-audit.md)
