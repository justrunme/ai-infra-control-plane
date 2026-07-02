# AI Infrastructure OS — Platform Demo

One command brings up the full **Control Plane + Execution Plane + Ollama** stack and verifies governance enforcement end-to-end.

```text
Client
  -> Execution Plane (gateway :8090)
  -> Control Plane (/governance/evaluate :8091)
  -> allow | block
  -> Ollama model backend
```

## Prerequisites

- Docker Compose v2
- Sibling checkout of [ai-runtime-platform](https://github.com/justrunme/ai-runtime-platform) at `../ai-runtime-platform` relative to this repo, **or** set `RUNTIME_PLATFORM_PATH`
- ~8 GB RAM and ~5 GB disk (Ollama image + `llama3.1:8b`)

## Start the platform

From the **ai-infra-control-plane** repository root:

```sh
make platform-demo
```

### Production overlay (Redis + Prometheus)

Shared tenant quota in Redis and live Prometheus governance inputs:

```sh
make platform-demo-production
make platform-demo-production-verify
```

| Service | URL |
| --- | --- |
| Prometheus | http://localhost:9090 |
| Redis | redis://localhost:6379/0 |

### Enterprise reference (production + OIDC)

Full stack for portfolio demos and architecture reviews:

```sh
make platform-demo-enterprise
make platform-demo-enterprise-verify
```

Combines Redis quota, Prometheus telemetry, Keycloak JWKS, and the full agentic governance verify path.

Or directly:

```sh
docker compose -f demo/platform/docker-compose.yaml up --build
```

| Service | URL | Role |
| --- | --- | --- |
| Control Plane | http://localhost:8091 | Dashboard, governance, drift |
| Execution Plane | http://localhost:8090 | OpenAI gateway with enforcement |
| Ollama | internal :11434 | Model backend |

## Verify end-to-end

With the stack running, in a second terminal:

```sh
make platform-demo-verify
```

### OIDC / Keycloak overlay

For signed JWT + JWKS verification with demo users `alice` / `bob`:

```sh
make platform-demo-oidc
make platform-demo-oidc-verify
```

See [docs/oidc-keycloak-demo.md](../../docs/oidc-keycloak-demo.md).

This script checks:

1. Governance **allow** for `platform` team
2. Governance **block** for `finance` + sensitive data quota
3. Gateway **200** completion when allowed
4. Gateway **403** when governance blocks
5. `/drift` inventory check
6. Prometheus metrics on both planes

## Manual curls

```sh
# Allowed inference path
curl -sS -X POST http://localhost:8090/v1/chat/completions \
  -H 'content-type: application/json' \
  -H 'x-ai-team: platform' \
  -H 'x-ai-namespace: ai-dev' \
  -d '{"model":"llama3.1:8b","messages":[{"role":"user","content":"hello"}],"max_tokens":16}'

# Blocked by governance
curl -sS -X POST http://localhost:8090/v1/chat/completions \
  -H 'content-type: application/json' \
  -H 'x-ai-team: finance' \
  -H 'x-ai-sensitive-data: true' \
  -H 'x-ai-requests-last-minute: 30' \
  -d '{"model":"llama3.1:8b","messages":[{"role":"user","content":"blocked"}],"max_tokens":8}'
```

Open the operator dashboard: http://localhost:8091/

## Stop

```sh
make platform-demo-down
```

## Custom runtime path

```sh
RUNTIME_PLATFORM_PATH=/path/to/ai-runtime-platform \
  docker compose -f demo/platform/docker-compose.yaml up --build
```
