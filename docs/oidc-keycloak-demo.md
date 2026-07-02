# Keycloak OIDC platform demo

End-to-end enterprise identity: **Keycloak → JWT → gateway JWKS verify → control-plane governance**.

## Start

```sh
make platform-demo-oidc
```

This overlays [docker-compose.oidc.yaml](../demo/platform/docker-compose.oidc.yaml) on the base platform demo and starts Keycloak on port **8180**.

| Service | URL |
| --- | --- |
| Keycloak | http://localhost:8180 |
| Control Plane | http://localhost:8091 |
| Gateway | http://localhost:8090 |

Demo users (password `demo`):

| User | Group | Expected governance |
| --- | --- | --- |
| `alice` | `platform` | allow |
| `bob` | `finance` | block on sensitive + high RPM |

## Verify

```sh
make platform-demo-oidc-verify
```

## Fetch a token manually

```sh
bash demo/platform/fetch-oidc-token.sh
OIDC_USERNAME=bob bash demo/platform/fetch-oidc-token.sh
```

## Architecture

```text
Client
  -> Keycloak (password grant, public client ai-gateway)
  -> Bearer JWT (groups claim)
  -> Gateway (OIDC_JWT_VERIFY + JWKS)
  -> Control Plane /governance/evaluate (forwards Authorization, JWKS verify)
  -> allow | block
```

Environment variables (set by the OIDC compose overlay):

| Variable | Value |
| --- | --- |
| `OIDC_JWT_VERIFY` | `true` |
| `OIDC_JWKS_URL` | `http://keycloak:8080/realms/ai-platform/protocol/openid-connect/certs` |
| `OIDC_JWT_ISSUER` | `http://localhost:8180/realms/ai-platform` |

## Related

- [Identity and audit trail](identity-audit.md)
- [Platform demo](../demo/platform/README.md)
