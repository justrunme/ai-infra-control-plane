# AI Infrastructure Control Plane

[![CI](https://github.com/justrunme/ai-infra-control-plane/actions/workflows/ci.yml/badge.svg)](https://github.com/justrunme/ai-infra-control-plane/actions/workflows/ci.yml)
[![Release](https://github.com/justrunme/ai-infra-control-plane/actions/workflows/release.yml/badge.svg)](https://github.com/justrunme/ai-infra-control-plane/actions/workflows/release.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-control%20API-009688)
![Kubernetes](https://img.shields.io/badge/Kubernetes-platform%20engineering-326CE5)
![Terraform](https://img.shields.io/badge/Terraform-infrastructure-844FBA)
![Trivy](https://img.shields.io/badge/Trivy-security%20scan-1904DA)
![License](https://img.shields.io/badge/license-MIT-green)

> **Product walkthrough** | Click the animated preview to watch the full 10-second platform overview.

[![Animated preview of the AI Infrastructure Control Plane](docs/videos/previews/hero-overview.gif)](docs/videos/hero-overview.mp4)

A Kubernetes-native platform for operating private AI workloads with observability, forecasting, GitOps delivery, security policy, cost governance, risk scoring, and human approval gates.

This project is intentionally scoped as an AI infrastructure platform, not an agent framework. It focuses on the platform engineering layer around Ollama, vLLM, OpenWebUI, and future private inference backends: deployment, health, latency, capacity, cost, dashboards, forecasting, policy, and operational readiness.

The core workflow is:

```text
AI request
  -> telemetry
  -> cost decision
  -> risk score
  -> approval decision
  -> final verdict
```

Read the portfolio overview in `docs/case-study.md` and the technical system design in `docs/platform-architecture.md`.

## Operator Dashboard

The control API serves a live operator dashboard at `/` with platform status,
topology health, and the model inventory, refreshed every few seconds.

![AI Infrastructure Control Plane operator dashboard](docs/images/operator-dashboard.png)

## How the Projects Fit Together

This repository is part of a larger AI Platform portfolio. Read the [portfolio overview](docs/portfolio-overview.md) for the full architecture.

| Layer | Responsibility | Repository |
| --- | --- | --- |
| **AI Infrastructure Control Plane** | Observes, governs, forecasts, and operates AI workloads through telemetry, policy, cost control, risk scoring, approvals, digital twin topology, and GitOps. | [justrunme/ai-infra-control-plane](https://github.com/justrunme/ai-infra-control-plane) |
| **AI Runtime Platform** | Executes private LLM inference through an OpenAI-compatible gateway, model routing, vLLM/Ollama, KServe, and KEDA. | [justrunme/ai-runtime-platform](https://github.com/justrunme/ai-runtime-platform) |

The Runtime Platform executes AI workloads. The Control Plane uses their operational signals to observe, govern, predict, and control the platform.

## Product Walkthroughs

### Governance Decision Flow

[![Animated preview of the AI governance decision flow](docs/videos/previews/governance-pipeline.gif)](docs/videos/governance-pipeline.mp4)

### AI Infrastructure Digital Twin

[![Animated preview of the AI infrastructure digital twin](docs/videos/previews/digital-twin.gif)](docs/videos/digital-twin.mp4)

### Forecast-driven Scaling

[![Animated preview of forecast-driven scaling](docs/videos/previews/forecast-driven-scaling.gif)](docs/videos/forecast-driven-scaling.mp4)

## Visual Overview

### Platform Overview

```mermaid
flowchart TB
    User["AI Consumer"]
    API["Control API<br/>FastAPI"]

    subgraph ControlPlane["AI Infrastructure Control Plane"]
        Capacity["Capacity Planner"]
        Cost["Cost Governance"]
        Risk["Risk Scoring"]
        Approval["Approval Engine"]
        Twin["Digital Twin"]
    end

    subgraph AI["AI Workloads"]
        Ollama["Ollama"]
        VLLM["vLLM"]
        Models["Foundation Models"]
    end

    subgraph Observability["Observability"]
        OTel["OpenTelemetry"]
        Prom["Prometheus"]
        Graf["Grafana"]
        Loki["Loki"]
    end

    User --> API
    API --> Capacity
    API --> Cost
    API --> Risk
    API --> Approval
    API --> Twin
    Capacity --> Ollama
    Capacity --> VLLM
    Ollama --> Models
    VLLM --> Models
    Ollama --> OTel
    VLLM --> OTel
    OTel --> Prom
    OTel --> Loki
    Prom --> Graf
    Loki --> Graf
    Twin --> Graf
```

### Governance Flow

```mermaid
flowchart LR
    Request["AI Request"]
    Cost["Cost Analysis"]
    Risk["Risk Analysis"]
    Capacity["Capacity Check"]
    Decision{"Policy Engine"}
    Allow["ALLOW"]
    Warn["WARN"]
    Block["BLOCK"]

    Request --> Cost
    Request --> Risk
    Request --> Capacity
    Cost --> Decision
    Risk --> Decision
    Capacity --> Decision
    Decision --> Allow
    Decision --> Warn
    Decision --> Block
```

### Digital Twin

```mermaid
flowchart LR
    Real["Real AI Cluster"]
    Metrics["Telemetry"]
    Twin["Digital Twin Model"]
    Simulate["Scenario Simulation"]
    Decision["Capacity Decision"]

    Real --> Metrics
    Metrics --> Twin
    Twin --> Simulate
    Simulate --> Decision
```

### Forecast-driven Scaling

```mermaid
flowchart TB
    Metrics["Historical Metrics"]
    TimesFM["TimesFM Forecasting"]
    Forecast["Demand Forecast"]
    ScaleUp["Scale Up"]
    ScaleDown["Scale Down"]

    Metrics --> TimesFM
    TimesFM --> Forecast
    Forecast --> ScaleUp
    Forecast --> ScaleDown
```

### GitOps Delivery

```mermaid
flowchart LR
    Dev["Developer"]
    Git["Git Repository"]
    Actions["GitHub Actions"]
    Registry["Container Registry"]
    Argo["Argo CD"]
    Cluster["Kubernetes Cluster"]

    Dev --> Git
    Git --> Actions
    Actions --> Registry
    Registry --> Argo
    Argo --> Cluster
```

## Scope

- Expose a control API for private AI backend health, latency, capacity, and cost signals.
- Monitor local and Kubernetes-hosted inference backends such as Ollama and vLLM.
- Package the API with Docker and Helm.
- Provision a small VM baseline with Terraform.
- Add GitOps deployment examples through Argo CD.
- Add security and quality gates through GitHub Actions.
- Add observability with Prometheus, Grafana, and future log signals.
- Explore experimental forecasting for latency, load, capacity, and cost signals.
- Evaluate AI governance decisions through cost controls, risk scoring, and approval gates.
- Grow through weekly issues and pull requests instead of empty commits.

## Repository Layout

```text
apps/
  control-api/        FastAPI service with health and model status endpoints
infra/
  helm/               Kubernetes packaging
  terraform/          Cloud bootstrap modules
    k3s-bootstrap/    Example Hetzner VM bootstrap with cloud-init and k3s
observability/
  grafana/            Dashboards and metrics notes
  loki/               Loki and Promtail logging examples
  otel-genai/         OpenTelemetry GenAI telemetry prototype
forecasting/
  timesfm/            Experimental capacity forecasting prototype
experiments/
  inference-autoscaling/ Forecast-driven inference scaling recommendations
governance/
  cost/               AI cost governance policy engine
  risk/               AI request risk scoring engine
  approval/           Human approval workflow prototype
  pipeline/           End-to-end AI governance decision pipeline
security/
  trivy/              Container and IaC scan configuration
  opa/                Kubernetes policy gates for rendered manifests
docs/
  architecture.md     System design notes
  case-study.md       Portfolio case study and demo flow
  digital-twin.md     AI infrastructure topology model
  platform-architecture.md Technical platform architecture
```

## Local Development

```sh
cd apps/control-api
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Run tests:

```sh
make venv
make test
```

The project targets Python 3.12 for local development and CI.

Run the portfolio demo:

```sh
make demo
```

The demo prints the key control API endpoints and runs the end-to-end governance pipeline from `governance/pipeline/sample_requests.csv`.

## Control API

The control API exposes operator-facing signals for private AI infrastructure:

- `GET /` - live operator dashboard (HTML).
- `GET /health` - operator-facing service health.
- `GET /healthz` - Kubernetes-compatible health check.
- `GET /models` - configured model backends and status.
- `GET /metrics` - Prometheus-compatible text metrics.
- `GET /capacity` - aggregate model serving capacity.
- `GET /cost` - estimated hourly, daily, and monthly cost.
- `GET /summary` - compact status for dashboards and demos.

### Model Inventory

The model inventory is configuration-driven. By default the API loads
`app/model_inventory.json` shipped with the image, but you can point it at any
JSON file:

```sh
export MODEL_INVENTORY_PATH=/etc/ai-control-plane/model_inventory.json
```

The file is a JSON array of model entries; see
`apps/control-api/examples/model_inventory.sample.json` for a multi-backend
example. If the file is missing or malformed, the API falls back to a built-in
inventory so the control plane stays observable.

### Ollama Backend Probe

Set `OLLAMA_BASE_URL` to point the control API at an Ollama backend:

```sh
export OLLAMA_BASE_URL=http://localhost:11434
```

The API exposes:

- `GET /backends/ollama/health` - backend reachability and status.
- `GET /backends/ollama/models` - model names returned by Ollama `/api/tags`.
- `GET /backends/ollama/latency` - lightweight latency measurement for `/api/tags`.

### vLLM Backend Probe

Set `VLLM_BASE_URL` to point the control API at a vLLM OpenAI-compatible server:

```sh
export VLLM_BASE_URL=http://localhost:8000
```

The API exposes:

- `GET /backends/vllm/health` - backend reachability and status.
- `GET /backends/vllm/models` - model ids returned by vLLM `/v1/models`.
- `GET /backends/vllm/latency` - lightweight latency measurement for `/v1/models`.

### Prometheus Metrics

`GET /metrics` exposes Prometheus-compatible metrics for request traffic, backend health, model inventory, capacity, and estimated cost.

Core metrics:

- `ai_control_http_requests_total`
- `ai_control_http_request_latency_ms`
- `ai_control_backend_up`
- `ai_control_backend_latency_ms`
- `ai_control_model_available`
- `ai_control_capacity_available`
- `ai_control_estimated_hourly_cost_usd`

### AI Infrastructure Digital Twin

`GET /topology` exposes a live platform graph for private AI infrastructure components, dependencies, health, telemetry, and operational signals. The Ollama and vLLM nodes reflect live backend probe results (healthy/degraded plus measured latency). See `docs/digital-twin.md`.

### AI Cost Governance

`governance/cost` evaluates model usage, team budgets, token spend, and forecasted monthly cost into `allow`, `warn`, or `block` decisions.

### AI Approval Workflow

`governance/approval` evaluates high-risk AI platform requests into `allow`, `approval_required`, or `block` decisions for human approval gates.

### AI Governance Layer

`governance/cost`, `governance/risk`, and `governance/approval` model cost control, risk scoring, and human approval gates for private AI infrastructure.

`governance/pipeline` connects those signals into an end-to-end decision flow: request telemetry, cost decision, risk score, approval decision, and final verdict.

Run the demo pipeline:

```sh
python3.12 governance/pipeline/run_pipeline.py \
  --requests governance/pipeline/sample_requests.csv
```

## Container Images

Every merge to `main` builds and pushes the control API image to GitHub Container Registry:

```text
ghcr.io/justrunme/ai-infra-control-plane:latest
ghcr.io/justrunme/ai-infra-control-plane:<git-sha>
```

Images are signed with cosign and accompanied by an SPDX SBOM artifact from the release workflow. Tag releases with `v*` (for example `v0.2.0`) to publish semver tags.

## Kubernetes Deployment

```sh
helm upgrade --install ai-control-plane infra/helm/ai-control-plane \
  --set image.repository=ghcr.io/justrunme/ai-infra-control-plane \
  --set image.tag=latest
```

The chart ships production defaults: non-root execution, read-only root filesystem, model inventory ConfigMap, HPA, PodDisruptionBudget, and optional ServiceMonitor, Ingress, and NetworkPolicy. See `infra/helm/ai-control-plane/README.md`.

## Portfolio Docs

- `docs/case-study.md` explains the problem, architecture, capabilities, governance pipeline, observability, forecasting, GitOps, security, and demo flow.
- `docs/platform-architecture.md` describes the system boundary, logical layers, control API, governance architecture, delivery path, and extension points.

## Remaining Backlog

See `docs/backlog.md` for the full roadmap. Next items: OpenWebUI health checks, gateway enforcement for governance verdicts, and live Prometheus integration for policy inputs.
