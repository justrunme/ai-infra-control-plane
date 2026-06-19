# AI Infrastructure Control Plane

A Kubernetes-native platform for operating private AI workloads, including model serving, observability, security, GitOps deployment, cost tracking, and capacity management.

The project is intentionally scoped as an AI infrastructure platform, not an agent framework. It focuses on the platform engineering layer around Ollama, vLLM, OpenWebUI, and future private inference backends: deployment, health, latency, metrics, dashboards, security checks, and operational readiness.

Each directory is a real engineering surface that can grow through focused pull requests: API, Helm, Terraform, observability, security, GitOps, and CI/CD.

## Scope

- Expose a control API for private AI backend health, latency, capacity, and cost signals.
- Monitor local and Kubernetes-hosted inference backends such as Ollama and vLLM.
- Package the API with Docker and Helm.
- Provision a small VM baseline with Terraform.
- Add GitOps deployment examples through Argo CD.
- Add security and quality gates through GitHub Actions.
- Add observability with Prometheus, Grafana, and future log signals.
- Explore experimental forecasting for latency, load, capacity, and cost signals.
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
  approval/           Human approval workflow prototype
security/
  trivy/              Container and IaC scan configuration
  opa/                Kubernetes policy gates for rendered manifests
docs/
  architecture.md     System design notes
  digital-twin.md     AI infrastructure topology model
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

## Control API

The control API exposes operator-facing signals for private AI infrastructure:

- `GET /health` - operator-facing service health.
- `GET /healthz` - Kubernetes-compatible health check.
- `GET /models` - configured model backends and status.
- `GET /metrics` - Prometheus-compatible text metrics.
- `GET /capacity` - aggregate model serving capacity.
- `GET /cost` - estimated hourly, daily, and monthly cost.
- `GET /summary` - compact status for dashboards and demos.

### Ollama Backend Probe

Set `OLLAMA_BASE_URL` to point the control API at an Ollama backend:

```sh
export OLLAMA_BASE_URL=http://localhost:11434
```

The API exposes:

- `GET /backends/ollama/health` - backend reachability and status.
- `GET /backends/ollama/models` - model names returned by Ollama `/api/tags`.
- `GET /backends/ollama/latency` - lightweight latency measurement for `/api/tags`.

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

`GET /topology` exposes a live platform graph for private AI infrastructure components, dependencies, health, telemetry, and operational signals. See `docs/digital-twin.md`.

### AI Cost Governance

`governance/cost` evaluates model usage, team budgets, token spend, and forecasted monthly cost into `allow`, `warn`, or `block` decisions.

### AI Approval Workflow

`governance/approval` evaluates high-risk AI platform requests into `allow`, `approval_required`, or `block` decisions for human approval gates.

## First Backlog

- Add vLLM backend probes.
- Add OpenWebUI service health checks.
- Add a Grafana dashboard for request latency and model availability.
- Add Argo CD application manifests.
- Add horizontal pod autoscaling based on CPU and request latency.
- Add Loki log collection examples.
- Add OPA policy checks for Kubernetes manifests.
- Add Terraform examples for Hetzner and local k3s bootstrap.
