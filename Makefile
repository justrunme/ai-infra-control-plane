PYTHON ?= python3.12

.PHONY: venv test lint validate docker-build helm-template demo platform-demo platform-demo-verify platform-demo-down platform-demo-oidc platform-demo-oidc-verify platform-demo-oidc-down

venv:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && pip install -r requirements-dev.txt

test:
	. .venv/bin/activate && cd apps/control-api && PYTHONPATH=. pytest
	. .venv/bin/activate && pytest tests experiments/capacity-loop/tests experiments/gpu-placement/tests experiments/finops-recommendations/tests

lint:
	. .venv/bin/activate && ruff check .

validate: lint test helm-template policy-check terraform-fmt

docker-build:
	docker build -f apps/control-api/Dockerfile -t ai-infra-control-plane:local .

helm-template:
	helm template ai-control-plane infra/helm/ai-control-plane

policy-check:
	helm template ai-control-plane infra/helm/ai-control-plane \
		--set metrics.serviceMonitor.enabled=true \
		--set ingress.enabled=true \
		--set networkPolicy.enabled=true > /tmp/rendered-manifests.yaml
	conftest test --policy security/opa/policies /tmp/rendered-manifests.yaml
	opa test security/opa/tests security/opa/policies -v

terraform-fmt:
	terraform -chdir=infra/terraform/hetzner-vm fmt -check -recursive
	terraform -chdir=infra/terraform/k3s-bootstrap fmt -check -recursive

demo:
	@echo "AI Infrastructure Control Plane demo"
	@echo
	@echo "Full platform (Control + Execution planes):"
	@echo "  make platform-demo"
	@echo
	@echo "Operator dashboard:"
	@echo "  GET /  (governance playground + inventory drift)"
	@echo
	@echo "Control API endpoints:"
	@echo "  GET /health"
	@echo "  GET /models"
	@echo "  GET /metrics"
	@echo "  GET /capacity"
	@echo "  GET /cost"
	@echo "  GET /topology"
	@echo "  GET /backends/ollama/health"
	@echo "  GET /backends/vllm/health"
	@echo
	@echo "Governance pipeline:"
	$(PYTHON) governance/pipeline/run_pipeline.py --requests governance/pipeline/sample_requests.csv

PLATFORM_COMPOSE = docker compose -f demo/platform/docker-compose.yaml
PLATFORM_OIDC_COMPOSE = docker compose -f demo/platform/docker-compose.yaml -f demo/platform/docker-compose.oidc.yaml

platform-demo:
	$(PLATFORM_COMPOSE) up --build

platform-demo-verify:
	bash demo/platform/verify-demo.sh

platform-demo-down:
	$(PLATFORM_COMPOSE) down

platform-demo-oidc:
	$(PLATFORM_OIDC_COMPOSE) up --build

platform-demo-oidc-verify:
	bash demo/platform/verify-oidc-demo.sh

platform-demo-oidc-down:
	$(PLATFORM_OIDC_COMPOSE) down
