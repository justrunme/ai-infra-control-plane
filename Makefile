PYTHON ?= python3.12

.PHONY: venv test lint validate docker-build helm-template demo

venv:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && pip install -r requirements-dev.txt

test:
	. .venv/bin/activate && cd apps/control-api && PYTHONPATH=. pytest
	. .venv/bin/activate && pytest tests

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
