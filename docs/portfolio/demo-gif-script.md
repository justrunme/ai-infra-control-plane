# Enterprise AI OS — Demo GIF Script

60–90 second screen recording for README, LinkedIn, and conference submissions.

## Setup before recording

```bash
# Terminal 1 — control plane repo
make platform-demo

# Wait for health
curl -fsS http://127.0.0.1:8091/healthz
curl -fsS http://127.0.0.1:8090/healthz
```

Terminal font: large (14–16pt), dark theme, no notifications.

## Scene 1 — Title card (3s)

Text overlay (or browser tab title):

> **AI Infrastructure OS**
> Control Plane + Execution Plane on Kubernetes

## Scene 2 — Architecture (8s)

Open `docs/portfolio/reference-architecture.md` or product roadmap diagram:

- Control Plane → governance
- Execution Plane → gateway + MCP + intent
- Redis + Prometheus + Keycloak in enterprise tier
- Highlight: **decision vs execution**

## Scene 2b — Enterprise demo (optional, 8s)

```bash
make platform-demo-enterprise
make platform-demo-enterprise-verify
```

Let production-demo Redis/Prometheus checks scroll briefly.

## Scene 3 — One-command demo (5s)

```bash
make platform-demo-verify
```

Let first 3–4 green `[platform-demo]` lines scroll (fast cut).

## Scene 4 — Governance allow/block (12s)

Split terminal or sequential:

```bash
# Allow
curl -sS -X POST http://127.0.0.1:8091/governance/evaluate \
  -H 'content-type: application/json' \
  -d '{"team":"platform","namespace":"ai-dev","model":"llama3.1:8b","provider":"ollama"}' \
  | jq '.final_verdict,.policy_pack'

# Block (finance + sensitive)
curl -sS -X POST http://127.0.0.1:8091/governance/evaluate \
  -H 'content-type: application/json' \
  -d '{"team":"finance","namespace":"ai-dev","model":"llama3.1:8b","provider":"ollama","sensitive_data":true,"requests_last_minute":30}' \
  | jq '.final_verdict,.stages.quota.decision'
```

Overlay text: **Policy → Quota → Registry → Verdict**

## Scene 5 — Intent Engine (10s)

```bash
curl -sS -X POST http://127.0.0.1:8091/intent/resolve \
  -H 'content-type: application/json' \
  -H 'x-ai-team: finance' \
  -d '{"message":"Generate quarterly revenue report","team":"finance","environment":"production","namespace":"ai-prod"}' \
  | jq '{intent, confidence, plan: .plan | {agent, model, region, tools}}'
```

Overlay: **Natural language → orchestration plan**

## Scene 6 — MCP Gateway (10s)

```bash
# Allow
curl -sS -X POST http://127.0.0.1:8090/mcp/tools/jira-read/call \
  -H 'content-type: application/json' -H 'x-ai-team: platform' \
  -d '{"action":"read","arguments":{"issue":"PROJ-1"}}' | jq '.status,.tool'

# Block delete
curl -sS -o /dev/null -w 'HTTP %{http_code}\n' \
  -X POST http://127.0.0.1:8090/mcp/tools/kubernetes-admin/call \
  -H 'content-type: application/json' -H 'x-ai-team: platform' \
  -d '{"action":"delete","arguments":{"resource":"pod/demo"}}'
```

Overlay: **Governed tool access**

## Scene 7 — Gateway chat + audit (12s)

```bash
curl -sS -X POST http://127.0.0.1:8090/v1/chat/completions \
  -H 'content-type: application/json' -H 'x-ai-team: platform' \
  -d '{"model":"llama3.1:8b","messages":[{"role":"user","content":"Say hello"}],"max_tokens":16}' \
  | jq '.choices[0].message.content'

curl -sS 'http://127.0.0.1:8091/audit/events?limit=3' | jq '.[0] | {team, final_verdict, model}'
```

## Scene 8 — Closing card (5s)

> **Open source · Kubernetes-native · Production governance**
>
> github.com/justrunme/ai-infra-control-plane
> github.com/justrunme/ai-runtime-platform

## Recording tips

- Resolution: 1920×1080 or 1280×720
- Use `jq` for readable JSON (install if needed)
- Speed up `platform-demo-verify` middle section 2× in post
- Optional: picture-in-picture webcam only for intro/outro
- Export as GIF (≤15MB) via `ffmpeg` or Kap — keep under 90s for social

## ffmpeg GIF export (optional)

```bash
ffmpeg -i demo.mp4 -vf "fps=10,scale=1280:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" -loop 0 demo.gif
```
