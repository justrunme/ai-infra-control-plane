# AI Infrastructure Control Plane

Portfolio-grade control plane for running local and private AI inference on Kubernetes.

The project is intentionally small at the start, but each directory is a real engineering surface that can grow through focused pull requests: API, Helm, Terraform, observability, security, and GitHub Actions.

## Scope

- Expose a control API for model gateway health, latency, capacity, and cost signals.
- Package the API with Docker and Helm.
- Provision a small VM baseline with Terraform.
- Add security and quality gates through GitHub Actions.
- Grow through weekly issues and pull requests instead of empty commits.

## Repository Layout

```text
apps/
  control-api/        FastAPI service with health and model status endpoints
infra/
  helm/               Kubernetes packaging
  terraform/          Cloud bootstrap modules
observability/
  grafana/            Dashboards and metrics notes
security/
  trivy/              Container and IaC scan configuration
docs/
  architecture.md     System design notes
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

The initial control API exposes:

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

## First Backlog

- Add real vLLM and Ollama backend probes.
- Add a Grafana dashboard for request latency and model availability.
- Add Argo CD application manifests.
- Add horizontal pod autoscaling based on CPU and request latency.
- Add Terraform examples for Hetzner and local k3s bootstrap.
