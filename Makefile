PYTHON ?= python3.12

.PHONY: venv test lint docker-build helm-template demo

venv:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && pip install -r requirements-dev.txt

test:
	. .venv/bin/activate && cd apps/control-api && PYTHONPATH=. pytest

lint:
	. .venv/bin/activate && ruff check .

docker-build:
	docker build -t ai-infra-control-plane:local apps/control-api

helm-template:
	helm template ai-control-plane infra/helm/ai-control-plane

demo:
	@echo "AI Infrastructure Control Plane demo"
	@echo
	@echo "Control API endpoints:"
	@echo "  GET /health"
	@echo "  GET /models"
	@echo "  GET /metrics"
	@echo "  GET /capacity"
	@echo "  GET /cost"
	@echo "  GET /topology"
	@echo
	@echo "Governance pipeline:"
	$(PYTHON) governance/pipeline/run_pipeline.py --requests governance/pipeline/sample_requests.csv
