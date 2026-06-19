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
cd apps/control-api
pytest
```

The project targets Python 3.12 for local development and CI.

## First Backlog

- Add real vLLM and Ollama backend probes.
- Add a Grafana dashboard for request latency and model availability.
- Add Argo CD application manifests.
- Add horizontal pod autoscaling based on CPU and request latency.
- Add Terraform examples for Hetzner and local k3s bootstrap.
