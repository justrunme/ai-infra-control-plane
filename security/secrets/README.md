# AI platform secrets (Vault + External Secrets Operator)

Reference manifests for syncing provider credentials and gateway API keys into Kubernetes without storing them in Helm values or Git.

## Layout

| Path | Purpose |
| --- | --- |
| `examples/cluster-secret-store-vault.yaml` | ClusterSecretStore pointing at Vault |
| `examples/external-secret-control-plane.yaml` | ExternalSecret for control plane credentials |
| `vault-policy.hcl` | Least-privilege Vault policy for the platform |

## Vault paths

```text
secret/ai-platform/
├── gateway/api_keys          → GATEWAY_API_KEYS
├── providers/openai_api_key  → OPENAI_API_KEY
├── providers/anthropic_api_key → ANTHROPIC_API_KEY (optional)
└── control-plane/audit_signing_key → AUDIT_SIGNING_KEY
```

## Enable in Helm

```yaml
secrets:
  externalSecrets:
    enabled: true
    secretStoreRef:
      name: vault-ai-platform
      kind: ClusterSecretStore
```

The chart renders an `ExternalSecret` and mounts the synced Kubernetes `Secret` through `envFrom` on the control-api Deployment. Set `EXTERNAL_SECRETS_ENABLED=true` so `/secrets/status` reports `backend: external-secrets`.

## Local demo

Copy `demo/platform/secrets.env.example` to `demo/platform/secrets.env` and set gateway keys for laptop demos. Never commit `secrets.env`.

## Related

- [Secrets management](../../docs/secrets-management.md)
- [Identity and audit](../../docs/identity-audit.md)
